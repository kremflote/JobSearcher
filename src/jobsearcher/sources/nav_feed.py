"""NAV pam-stilling-feed source (ARCHITECTURE §4.3, spike 01).

The feed is an event log: every change to an ad adds a feed item, and the newest item for
an ad is its current state. Feed items are small summaries (uuid, status, title, business
name, municipality, sistEndret). The full ad (`ad_content`) needs one request per ad
(`GET /api/v1/feedentry/{id}`), so:

1. `collect` walks the feed pages from the stored cursor and emits one summary `RawJob` per
   ad (latest item wins). ACTIVE ads get `needs_detail=True`; INACTIVE ads get
   `active=False` so the pipeline can deactivate them.
2. `fetch_details` fetches `ad_content` only for the jobs the pipeline passes it (new jobs
   that passed the hard filter) and fills the structured fields.

Cursor key "feed": `cursor` is the relative URL of the next page to read, `etag` the ETag of
that page when it was the (incomplete) last page. The first run starts `initial_days_back`
days back with `If-Modified-Since` on `/api/v1/feed`.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, date, datetime, timedelta
from email.utils import format_datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from jobsearcher.sources.base import CollectResult, CursorState, RawContact, RawJob
from jobsearcher.sources.http import HttpClient, save_raw

log = logging.getLogger(__name__)

CURSOR_KEY = "feed"
DEFAULT_BASE_URL = "https://pam-stilling-feed.nav.no"
FEED_PATH = "/api/v1/feed"
ENTRY_PATH = "/api/v1/feedentry/{id}"
AD_URL = "https://arbeidsplassen.nav.no/stillinger/stilling/{uuid}"
DEFAULT_MAX_PAGES = 200
DEFAULT_DAYS_BACK = 30
PARSE_FAIL_WARN_RATIO = 0.2
OSLO = ZoneInfo("Europe/Oslo")


class _HttpFail(Exception):
    def __init__(self, status: int) -> None:
        super().__init__(f"HTTP {status}")
        self.status = status


def _status_message(status: int) -> str:
    if status in (401, 403):
        return f"NAV-feeden svarte {status}: token utløpt?"
    return f"NAV-feeden svarte {status}"


# --- parsing helpers -------------------------------------------------------------


def parse_datetime(value: Any) -> datetime | None:
    """ISO timestamp → aware UTC. Naive values are NAV local time (Europe/Oslo)."""
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=OSLO)
    return dt.astimezone(UTC)


_DMY = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")


def parse_deadline(value: Any) -> tuple[date | None, str | None]:
    """`applicationDue` → (date, None) for a date, (None, text) for e.g. "Snarest"."""
    if not value or not isinstance(value, str):
        return None, None
    s = value.strip()
    if not s:
        return None, None
    try:
        return date.fromisoformat(s[:10]), None
    except ValueError:
        pass
    m = _DMY.match(s)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1))), None
        except ValueError:
            pass
    return None, s


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def item_to_rawjob(item: dict[str, Any], base_url: str = DEFAULT_BASE_URL) -> RawJob:
    """Feed item (FeedLine) → summary RawJob. Raises on a malformed item."""
    entry = item["_feed_entry"]
    uuid = entry["uuid"]
    active = entry.get("status") == "ACTIVE"
    title = _clean(entry.get("title")) or _clean(item.get("title")) or ""
    detail_url = _clean(item.get("url")) or ENTRY_PATH.format(id=uuid)
    if detail_url.startswith("/"):
        detail_url = base_url.rstrip("/") + detail_url
    return RawJob(
        source="nav",
        source_id=uuid,
        url=AD_URL.format(uuid=uuid),
        title=title,
        company=_clean(entry.get("businessName")),
        municipality=_clean(entry.get("municipal")),
        active=active,
        needs_detail=active,
        prefiltered=False,
        meta={
            "detail_url": detail_url,
            "feed_item_id": item.get("id"),
            "status": entry.get("status"),
            "sist_endret": entry.get("sistEndret") or item.get("date_modified"),
        },
    )


def _occupations(ad: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for occ in ad.get("occupationCategories") or []:
        for key in ("level1", "level2"):
            name = _clean(occ.get(key))
            if name and name not in out:
                out.append(name)
    return out


def _contacts(ad: dict[str, Any]) -> list[RawContact]:
    out: list[RawContact] = []
    for c in ad.get("contactList") or []:
        name = _clean(c.get("name"))
        email = _clean(c.get("email"))
        phone = _clean(c.get("phone"))
        if not (name or email or phone):
            continue
        role = " – ".join(x for x in (_clean(c.get("title")), _clean(c.get("role"))) if x) or None
        out.append(RawContact(name=name or email or phone or "", role=role, email=email, phone=phone))
    return out


_REMOTE_MAP = {"hjemmekontor": "full", "hybridkontor": "hybrid", "hybrid": "hybrid", "remote": "full"}


def apply_ad_content(job: RawJob, ad: dict[str, Any]) -> RawJob:
    """Fill a RawJob from a FeedAd (`ad_content`)."""
    job.title = _clean(ad.get("title")) or job.title
    employer = ad.get("employer") or {}
    job.company = _clean(employer.get("name")) or job.company
    job.org_number = _clean(employer.get("orgnr"))
    locs = ad.get("workLocations") or []
    if locs:
        first = locs[0]
        job.municipality = _clean(first.get("municipal")) or job.municipality
        job.county = _clean(first.get("county"))
        job.country = _clean(first.get("country"))
        places: list[str] = []
        for loc in locs:
            p = _clean(loc.get("city")) or _clean(loc.get("municipal")) or _clean(loc.get("county"))
            if p and p not in places:
                places.append(p)
        job.location_text = ", ".join(places) or None
    job.published_at = parse_datetime(ad.get("published"))
    job.expires_at = parse_datetime(ad.get("expires"))
    job.deadline, job.deadline_text = parse_deadline(ad.get("applicationDue"))
    job.application_url = _clean(ad.get("applicationUrl")) or _clean(ad.get("sourceurl"))
    job.description_html = _clean(ad.get("description"))
    job.employment_type = _clean(ad.get("engagementtype"))
    job.occupation = _occupations(ad)
    job.contacts = _contacts(ad)
    if _clean(ad.get("link")):
        job.url = ad["link"]

    meta = job.meta
    for key in ("sector", "extent", "engagementtype", "positioncount", "starttime", "jobtitle", "source"):
        if _clean(ad.get(key)):
            meta[key] = ad[key]
    if ad.get("workLanguage"):
        meta["workLanguage"] = ad["workLanguage"]
    for key in ("remote", "homeOffice"):
        if ad.get(key):
            meta[key] = ad[key]
            remote = _REMOTE_MAP.get(str(ad[key]).strip().lower())
            if remote and job.remote is None:
                job.remote = remote  # type: ignore[assignment]
    if _clean(employer.get("description")):
        meta["employer_description"] = employer["description"]
    if _clean(employer.get("homepage")):
        meta["employer_homepage"] = employer["homepage"]
    if ad.get("categoryList"):
        meta["categories"] = [
            {"type": c.get("categoryType"), "code": c.get("code"), "name": c.get("name")}
            for c in ad["categoryList"]
        ]
    meta["occupation"] = job.occupation
    if job.country:
        meta["country"] = job.country
    if _clean(ad.get("updated")):
        meta["updated"] = ad["updated"]
    job.needs_detail = False
    return job


# --- source ----------------------------------------------------------------------


class NavFeedSource:
    name = "nav"

    def __init__(self, http: HttpClient, config: dict, token: str) -> None:
        self.http = http
        self.config = config or {}
        self.token = token
        self.base_url = str(self.config.get("base_url") or DEFAULT_BASE_URL).rstrip("/")
        self.days_back = int(self.config.get("initial_days_back", DEFAULT_DAYS_BACK))
        self.max_pages = int(self.config.get("max_pages_per_run", DEFAULT_MAX_PAGES))
        # NAV's gateway answers slowly (13–60 s per feed page, spike 01).
        self.timeout_s = float(self.config.get("timeout_s", 90))
        # A struggling NAV gateway is not helped by quick retries; try again next run.
        self.retries = int(self.config.get("retries", 0))

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}

    def _abs(self, url: str) -> str:
        return url if url.startswith("http") else self.base_url + (url if url.startswith("/") else "/" + url)

    def _get(self, url: str, **kwargs: Any) -> httpx.Response:
        # The API is not a website; robots.txt does not apply to authenticated API calls.
        kwargs.setdefault("timeout", self.timeout_s)
        kwargs.setdefault("retries", self.retries)
        return self.http.get(self._abs(url), headers=self._headers(), respect_robots=False, **kwargs)

    # --- collect -----------------------------------------------------------------

    def collect(self, state: dict[str, CursorState]) -> CollectResult:
        result = CollectResult()
        if not self.token:
            result.health = "fail"
            result.message = "NAV_FEED_TOKEN mangler i .env"
            result.errors.append(result.message)
            return result
        prev = state.get(CURSOR_KEY) or CursorState()
        cursor = CursorState(cursor=prev.cursor, etag=prev.etag)
        first_run = cursor.cursor is None
        latest: dict[str, RawJob] = {}
        items_seen = 0
        parse_fail = 0
        pages = 0
        reached_end = False
        try:
            while pages < self.max_pages:
                if cursor.cursor is None:
                    since = datetime.now(UTC) - timedelta(days=self.days_back)
                    r = self._get(FEED_PATH, last_modified=format_datetime(since, usegmt=True))
                else:
                    r = self._get(cursor.cursor, etag=cursor.etag)
                pages += 1
                if r.status_code == 304:
                    reached_end = True
                    break
                if r.status_code >= 400:
                    raise _HttpFail(r.status_code)
                page = r.json()
                page_id = page.get("id") or f"page{pages}"
                raw_path = save_raw(self.name, f"feed_{page_id}.json", r.text)
                for item in page.get("items") or []:
                    items_seen += 1
                    try:
                        job = item_to_rawjob(item, self.base_url)
                    except Exception as e:  # noqa: BLE001
                        parse_fail += 1
                        log.warning("nav feed item parse failed: %s", e)
                        continue
                    job.raw_path = raw_path
                    latest.pop(job.source_id, None)  # keep insertion order = newest last
                    latest[job.source_id] = job
                if pages % 10 == 0:
                    log.info("nav feed: %d pages, %d items", pages, items_seen)
                next_url = page.get("next_url")
                if next_url and page.get("next_id") != page.get("id"):
                    cursor = CursorState(cursor=next_url, etag=None)
                    continue
                # End of the feed: re-poll this page next run, with its ETag.
                cursor = CursorState(
                    cursor=page.get("feed_url") or cursor.cursor or f"{FEED_PATH}/{page_id}",
                    etag=r.headers.get("ETag"),
                )
                reached_end = True
                break
        except _HttpFail as e:
            msg = _status_message(e.status)
            return self._partial(result, latest, cursor, prev, pages, msg)
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as e:
            msg = f"NAV-feeden feilet: {type(e).__name__}: {e}"
            return self._partial(result, latest, cursor, prev, pages, msg)
        except Exception as e:  # noqa: BLE001
            log.exception("nav collect failed")
            msg = f"NAV-feeden feilet: {type(e).__name__}: {e}"
            return self._partial(result, latest, cursor, prev, pages, msg)

        result.jobs = list(latest.values())
        result.found = len(result.jobs)
        result.state = {CURSOR_KEY: cursor}
        if parse_fail and parse_fail > PARSE_FAIL_WARN_RATIO * max(items_seen, 1):
            result.health = "warn"
            result.message = f"NAV: {parse_fail} av {items_seen} feed-elementer kunne ikke tolkes"
        elif first_run and items_seen == 0:
            result.health = "warn"
            result.message = "NAV-feeden ga 0 annonser ved første kjøring"
        elif not reached_end:
            result.message = f"NAV: {pages} sider lest (maks per kjøring), fortsetter neste kjøring"
        else:
            result.message = f"NAV: {result.found} annonser fra {pages} sider"
        if parse_fail:
            result.errors.append(f"{parse_fail} feed-elementer kunne ikke tolkes")
        return result

    def _partial(
        self,
        result: CollectResult,
        latest: dict[str, RawJob],
        cursor: CursorState,
        prev: CursorState,
        pages: int,
        msg: str,
    ) -> CollectResult:
        """Error mid-walk: keep what we got and the cursor of the page that failed."""
        log.warning("nav collect: %s", msg)
        result.jobs = list(latest.values())
        result.found = len(result.jobs)
        result.errors.append(msg)
        result.message = msg
        if result.jobs:
            # Earlier pages succeeded: progress is real, resume from the failing page.
            result.health = "warn"
            result.state = {CURSOR_KEY: cursor}
        else:
            result.health = "fail"
            result.state = {CURSOR_KEY: prev}
        return result

    # --- details -----------------------------------------------------------------

    def fetch_details(self, jobs: list[RawJob]) -> list[RawJob]:
        for job in jobs:
            if job.source != self.name or not job.needs_detail:
                continue
            try:
                self._fill_detail(job)
            except Exception as e:  # noqa: BLE001
                log.warning("nav detail %s failed: %s", job.source_id, e)
        return jobs

    def _fill_detail(self, job: RawJob) -> None:
        url = (job.meta or {}).get("detail_url") or ENTRY_PATH.format(id=job.source_id)
        r = self._get(url)
        if r.status_code >= 400:
            raise _HttpFail(r.status_code)
        body = r.json()
        ad = body.get("ad_content")
        if body.get("status") and body["status"] != "ACTIVE":
            job.active = False
            job.meta["status"] = body["status"]
        if not ad:
            job.needs_detail = False
            return
        apply_ad_content(job, ad)


__all__ = ["NavFeedSource", "item_to_rawjob", "apply_ad_content", "parse_deadline", "parse_datetime"]
