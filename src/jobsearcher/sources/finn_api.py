"""Finn via the mobile app gateway (ARCHITECTURE §4.2, spike 04).

Two steps:
1. `collect`: signed `GET /search/{searchkey}` per configured search, newest first, until the
   per-search cursor (highest seen `published`, ms epoch) is reached. No ad text.
2. `fetch_details`: plain GET of the public ad page; the JSON-LD `JobPosting` gives the text.

Politeness (§4.2 "Hensyn til Finn"): jittered spacing per host, a cap on ad pages per run,
back off on 403/429, a cooldown between runs, weekly searches where daily adds nothing, and
cached filter metadata. Ad pages are requested the way the app's WebView opens them.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from selectolax.lexbor import LexborHTMLParser

from jobsearcher.api.schemas import JobType
from jobsearcher.config import env
from jobsearcher.sources.base import CollectResult, CursorState, RawJob
from jobsearcher.sources.finn_sig import sign_url
from jobsearcher.sources.http import HttpClient, save_raw

log = logging.getLogger(__name__)

GW_BASE = "https://appsgw.finn.no"
GW_HOST = "appsgw.finn.no"
WEB_HOST = "www.finn.no"
AD_URL = "https://www.finn.no/job/ad/{id}"
SERVICE = "Search-Quest-JB"
CLIENT = "android-finn"
# App identity pinned to the APK the gateway was reverse engineered from (spike 04).
APP_VERSION = "261006-ec709768"
APP_BUILD = "1005273389"
APP_PACKAGE = "no.finn.android"
# Device the app identity claims to run on; the WebView User-Agent must agree with it.
OS_VERSION = "14"
DEVICE_MODEL = "Pixel 8"
DEVICE_BUILD = "AP2A.240805.005"
WEBVIEW_CHROME = "129.0.6668.100"
DEVICE_FILE = "finn_device.json"
FILTERS_FILE = "finn_filters.json"

INITIAL_MAX_PAGES = 3
MAX_PAGES = 10
GATEWAY_INTERVAL_S = (2.0, 4.0)
AD_PAGE_INTERVAL_S = (5.0, 10.0)
MAX_DETAILS_PER_RUN = 40
FILTER_CHECK_DAYS = 7.0
MIN_HOURS_BETWEEN_RUNS = 3.0
# A weekly search is due a little early, so the daily start jitter never pushes it a day.
_EVERY_DAYS_SLACK = timedelta(hours=2)
# Specific job types win over permanent when the same ad comes from several searches.
_TYPE_RANK: dict[str, int] = {"unknown": 0, "permanent": 1, "trainee": 2, "graduate": 2, "summer": 2}
# Params that are not filters (never validated against filter metadata).
_NON_FILTER_PARAMS = {"q", "sort", "page", "client", "include_filters", "include_results"}
_APPLY_RE = re.compile(r'href="(https://www\.finn\.no/job-apply/\d+/apply)"')


# --- time helpers ----------------------------------------------------------------


def _ms_to_utc(ms: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _last_sunday_1utc(year: int, month: int) -> datetime:
    d = datetime(year, month + 1, 1, 1, tzinfo=UTC) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def _oslo_date(dt: datetime) -> date:
    """Calendar date in Europe/Oslo. Falls back to the EU DST rule without tzdata."""
    try:
        from zoneinfo import ZoneInfo

        return dt.astimezone(ZoneInfo("Europe/Oslo")).date()
    except Exception:  # noqa: BLE001  (ZoneInfoNotFoundError on Windows without tzdata)
        dst = _last_sunday_1utc(dt.year, 3) <= dt < _last_sunday_1utc(dt.year, 10)
        return (dt + timedelta(hours=2 if dst else 1)).date()


def _parse_iso_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        if len(value) == 10:
            return date.fromisoformat(value)
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return _oslo_date(dt) if dt.tzinfo else dt.date()
    except ValueError:
        return None


# --- device identity -------------------------------------------------------------

_DEVICE_KEYS = ("installation_id", "ab_test_device_id")


def device_ids() -> dict[str, str]:
    """Installation/visitor UUID and A/B-test device UUID, generated once and kept in
    DATA_DIR/finn_device.json like an app install. Missing keys are added, never replaced."""
    path = env().data_dir / DEVICE_FILE
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(stored, dict):
            stored = {}
    except (OSError, ValueError):
        stored = {}
    out: dict[str, str] = {}
    changed = False
    for key in _DEVICE_KEYS:
        try:
            out[key] = str(uuid.UUID(str(stored[key])))
        except (KeyError, ValueError, TypeError):
            out[key] = str(uuid.uuid4())
            changed = True
    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({**stored, **out}), encoding="utf-8")
    return out


def device_id() -> str:
    """Installation/visitor UUID (see `device_ids`)."""
    return device_ids()["installation_id"]


# --- parsing -----------------------------------------------------------------------


def _as_list(v: Any) -> list[str]:
    if v is None:
        return []
    return [str(x) for x in v] if isinstance(v, list | tuple) else [str(v)]


def doc_to_rawjob(doc: dict[str, Any], search_id: str, job_type: JobType | None) -> RawJob:
    """Map one search doc to a RawJob. Raises KeyError/ValueError when id or heading is missing."""
    ad_id = str(doc.get("id") or doc["ad_id"])
    title = doc.get("heading") or doc.get("job_title")
    if not title:
        raise ValueError(f"Finn-annonse {ad_id} mangler tittel")
    county = municipality = country = None
    wl = doc.get("work_locations") or []
    if wl and isinstance(wl[0], list) and len(wl[0]) >= 3:
        country, county = wl[0][0], wl[0][1]
        # [country, county, municipality, place]; for Oslo the third element is a district.
        municipality = "Oslo" if county == "Oslo" else wl[0][2]
    published = _ms_to_utc(doc.get("published") or doc.get("timestamp"))
    deadline_dt = _ms_to_utc(doc.get("deadline"))
    meta: dict[str, Any] = {
        "finn_searches": [search_id],
        "job_title": doc.get("job_title"),
        "no_of_positions": doc.get("no_of_positions"),
        "extras": {e["id"]: e.get("values", []) for e in doc.get("extras") or [] if "id" in e},
        "work_locations": wl,
    }
    if doc.get("compensation"):
        meta["compensation"] = doc["compensation"]
    return RawJob(
        source="finn_api",
        source_id=ad_id,
        url=AD_URL.format(id=ad_id),
        title=title,
        company=doc.get("company_name"),
        location_text=doc.get("location"),
        municipality=municipality,
        county=county,
        country=country,
        published_at=published,
        deadline=_oslo_date(deadline_dt) if deadline_dt else None,
        job_type_hint=job_type,
        prefiltered=True,
        needs_detail=True,
        description_html=None,
        meta=meta,
    )


def _merge(existing: RawJob, new: RawJob) -> None:
    for sid in new.meta["finn_searches"]:
        if sid not in existing.meta["finn_searches"]:
            existing.meta["finn_searches"].append(sid)
    old_t, new_t = existing.job_type_hint, new.job_type_hint
    if new_t and _TYPE_RANK.get(new_t, 0) > _TYPE_RANK.get(old_t or "unknown", 0):
        existing.job_type_hint = new_t


def parse_job_posting(html: str) -> dict[str, Any] | None:
    """Return the JobPosting object from the ad page's JSON-LD (Finn wraps it in
    {"script:ld+json": {...}})."""
    tree = LexborHTMLParser(html)
    for node in tree.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(node.text() or "")
        except ValueError:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("script:ld+json"), dict):
                item = item["script:ld+json"]
            graph = item.get("@graph") if isinstance(item, dict) else None
            for obj in graph if isinstance(graph, list) else [item]:
                if isinstance(obj, dict) and obj.get("@type") == "JobPosting":
                    return obj
    return None


def _apply_url(html: str) -> str | None:
    node = LexborHTMLParser(html).css_first("a.job-apply-button")
    href = node.attributes.get("href") if node else None
    if href:
        return href
    m = _APPLY_RE.search(html)
    return m.group(1) if m else None


def _filter_values(filters: list[dict[str, Any]]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}

    def walk(name: str, items: list[dict[str, Any]]) -> None:
        for it in items or []:
            if "value" in it:
                out.setdefault(name, set()).add(str(it["value"]))
            walk(name, it.get("filter_items") or [])

    for f in filters or []:
        out.setdefault(f.get("name", ""), set())
        walk(f.get("name", ""), f.get("filter_items") or [])
    return out


def _interval(value: Any, default: tuple[float, float]) -> float | tuple[float, float]:
    """Config value `[min, max]` or a number → HttpClient interval."""
    if value is None:
        return default
    if isinstance(value, list | tuple):
        return (float(value[0]), float(value[-1]))
    return float(value)


# --- source --------------------------------------------------------------------------


class _HttpFail(Exception):
    def __init__(self, status: int, what: str) -> None:
        super().__init__(f"{what} svarte {status}")
        self.status = status


class FinnApiSource:
    name = "finn_api"

    def __init__(self, http: HttpClient, config: dict) -> None:
        self.http = http
        self.config = config or {}
        self.base_url = str(self.config.get("base_url", GW_BASE)).rstrip("/")
        self.app_version = str(self.config.get("app_version", APP_VERSION))
        self.app_build = str(self.config.get("app_build", APP_BUILD))
        self.os_version = str(self.config.get("os_version", OS_VERSION))
        self.device_model = str(self.config.get("device_model", DEVICE_MODEL))
        self.device_build = str(self.config.get("device_build", DEVICE_BUILD))
        self.webview_chrome = str(self.config.get("webview_chrome_version", WEBVIEW_CHROME))
        self.initial_max_pages = int(self.config.get("initial_max_pages", INITIAL_MAX_PAGES))
        self.max_pages = int(self.config.get("max_pages", MAX_PAGES))
        self.max_details_per_run = int(self.config.get("max_details_per_run", MAX_DETAILS_PER_RUN))
        self.min_hours_between_runs = float(
            self.config.get("min_hours_between_runs", MIN_HOURS_BETWEEN_RUNS)
        )
        self.validate_filters = bool(self.config.get("validate_filters", True))
        self.filter_check_days = float(self.config.get("filter_check_days", FILTER_CHECK_DAYS))
        self.force = bool(self.config.get("force", False))
        self.detail_message: str | None = None
        self._ids: dict[str, str] | None = None
        self._session_id = str(uuid.uuid4())
        # The source owns the spacing for its own hosts (jittered, see HttpClient).
        http.set_interval(GW_HOST, _interval(self.config.get("gateway_interval_s"), GATEWAY_INTERVAL_S))
        http.set_interval(WEB_HOST, _interval(self.config.get("ad_page_interval_s"), AD_PAGE_INTERVAL_S))

    # --- request helpers -------------------------------------------------------

    def _device(self) -> dict[str, str]:
        if self._ids is None:
            self._ids = device_ids()
        return self._ids

    def _headers(self) -> dict[str, str]:
        """App gateway headers, as `GeneralHeaderInterceptor` sets them (spike 04)."""
        ids = self._device()
        return {
            "User-Agent": (
                f"FINN/{self.app_version} (Android {self.os_version}; FINN-Device-Info: Android, mobile)"
            ),
            "FINN-Device-Info": "Android, mobile",
            "FINN-App-Installation-Id": ids["installation_id"],
            "Visitor-Id": ids["installation_id"],
            "Session-Id": self._session_id,
            "Ab-Test-Device-Id": ids["ab_test_device_id"],
            "Build-Type": "release",
            "VersionCode": self.app_build,
            "X-FINN-API-Version": "5",
            "x-nmp-os-name": "Android",
            "x-nmp-os-version": self.os_version,
            "x-nmp-device": self.device_model,
            "x-nmp-app-brand": "FINN",
            "x-nmp-app-version-name": self.app_version,
            "x-nmp-app-build-number": self.app_build,
            "CMP-Advertising": "0",
            "CMP-Analytics": "0",
            "CMP-Marketing": "0",
            "CMP-Personalisation": "0",
            "FINN-GW-Service": SERVICE,
        }

    def _web_headers(self) -> dict[str, str]:
        """Ad page headers. The app opens ads in an Android WebView, so look like one."""
        return {
            "User-Agent": (
                f"Mozilla/5.0 (Linux; Android {self.os_version}; {self.device_model} "
                f"Build/{self.device_build}; wv) AppleWebKit/537.36 (KHTML, like Gecko) "
                f"Version/4.0 Chrome/{self.webview_chrome} Mobile Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
                "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
            ),
            "Accept-Language": "nb-NO,nb;q=0.9,no;q=0.8,en-US;q=0.7,en;q=0.6",
            "Upgrade-Insecure-Requests": "1",
            "X-Requested-With": APP_PACKAGE,
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
        }

    def _gw_get(self, searchkey: str, params: list[tuple[str, str]]) -> dict[str, Any]:
        url = f"{self.base_url}/search/{searchkey}?{urlencode(params)}"
        headers = self._headers()
        headers["FINN-GW-KEY"] = sign_url("GET", url, SERVICE)
        r = self.http.get(url, headers=headers, respect_robots=False)
        if r.status_code >= 400:
            raise _HttpFail(r.status_code, "Finn")
        return r.json()

    def _search_params(self, search: dict[str, Any]) -> dict[str, list[str]]:
        params: dict[str, list[str]] = {
            k: _as_list(v) for k, v in (self.config.get("common_params") or {}).items()
        }
        for k, v in (search.get("params") or {}).items():
            params[k] = _as_list(v)
        return params

    # --- scheduling ------------------------------------------------------------

    def _cooldown_left(self, state: dict[str, CursorState], now: datetime) -> timedelta | None:
        """Time left before Finn may be asked again, or None when a run is allowed."""
        if self.force or self.min_hours_between_runs <= 0:
            return None
        stamps = [_aware(s.last_success_at) for s in state.values() if s.last_success_at]
        if not stamps:
            return None
        left = max(stamps) + timedelta(hours=self.min_hours_between_runs) - now
        return left if left > timedelta(0) else None

    def _due(self, search: dict[str, Any], old: CursorState, now: datetime) -> bool:
        """False for a search with `every_days` that ran successfully too recently."""
        every = float(search.get("every_days") or 0)
        if self.force or every <= 0 or old.last_success_at is None:
            return True
        return now - _aware(old.last_success_at) >= timedelta(days=every) - _EVERY_DAYS_SLACK

    # --- collect ---------------------------------------------------------------

    def collect(self, state: dict[str, CursorState]) -> CollectResult:
        now = datetime.now(UTC)
        left = self._cooldown_left(state, now)
        if left is not None:
            minutes = int(left.total_seconds() // 60) + 1
            return CollectResult(
                skipped=True,
                message=f"Finn hoppet over: hentet nylig, tidligst igjen om {minutes} min",
            )

        result = CollectResult()
        jobs: dict[str, RawJob] = {}
        searches: dict[str, dict[str, Any]] = {
            sid: s
            for sid, s in (self.config.get("searches") or {}).items()
            if self._due(s, state.get(sid) or CursorState(), now)
        }
        total_docs = failed_docs = raw_hits = 0
        warnings: list[str] = []
        fail_msg: str | None = None

        if self.validate_filters and searches:
            try:
                warnings += self._check_filters(searches)
            except Exception as e:  # noqa: BLE001
                warnings.append(f"Kunne ikke sjekke Finn-filtre: {e}")

        for search_id, search in searches.items():
            old = state.get(search_id) or CursorState()
            try:
                docs, new_cursor, hits = self._collect_search(search_id, search, old.cursor)
                raw_hits += hits
            except _HttpFail as e:
                msg = f"Finn svarte {e.status} på søk {search_id}"
                if e.status in (401, 403):
                    msg = f"Finn svarte {e.status}: signaturen kan være rotert"
                elif e.status == 429:
                    msg = "Finn svarte 429 (for mange forespørsler): stoppet til neste kjøring"
                result.errors.append(msg)
                fail_msg = fail_msg or msg
                if e.status in (401, 403, 429):
                    break  # every search will fail the same way; don't push on
                continue
            except Exception as e:  # noqa: BLE001
                msg = f"Finn-søk {search_id} feilet: {type(e).__name__}: {e}"
                log.exception("finn search %s failed", search_id)
                result.errors.append(msg)
                fail_msg = fail_msg or msg
                continue
            result.state[search_id] = CursorState(cursor=new_cursor, etag=old.etag)
            job_type = search.get("job_type")
            for doc in docs:
                total_docs += 1
                try:
                    job = doc_to_rawjob(doc, search_id, job_type)
                except (KeyError, ValueError, TypeError) as e:
                    failed_docs += 1
                    log.warning("finn doc parse failed: %s", e)
                    continue
                if job.source_id in jobs:
                    _merge(jobs[job.source_id], job)
                else:
                    jobs[job.source_id] = job

        result.jobs = list(jobs.values())
        result.found = len(result.jobs)
        if failed_docs:
            result.errors.append(f"{failed_docs} av {total_docs} Finn-annonser kunne ikke leses")
        result.errors += warnings
        if fail_msg:
            result.health, result.message = "fail", fail_msg
        elif total_docs and failed_docs / total_docs > 0.2:
            result.health = "warn"
            result.message = f"{failed_docs} av {total_docs} Finn-annonser kunne ikke leses"
        elif searches and raw_hits == 0:
            result.health, result.message = "warn", "Ingen treff på noen Finn-søk"
        elif warnings:
            result.health, result.message = "warn", warnings[0]
        else:
            result.health = "ok"
            result.message = f"{result.found} nye annonser fra Finn"
        return result

    def _collect_search(
        self, search_id: str, search: dict[str, Any], cursor: str | None
    ) -> tuple[list[dict[str, Any]], str | None, int]:
        """Return (docs newer than cursor, new cursor, docs returned by Finn incl. old ones)."""
        searchkey = search.get("searchkey", "SEARCH_ID_JOB_FULLTIME")
        base = [(k, v) for k, vals in self._search_params(search).items() for v in vals]
        base = [("client", CLIENT), *base, ("sort", "PUBLISHED_DESC")]
        cursor_ms = int(cursor) if cursor and cursor.isdigit() else None
        max_pages = self.max_pages if cursor_ms is not None else self.initial_max_pages
        newest = cursor_ms
        out: list[dict[str, Any]] = []
        hits = 0
        for page in range(1, max_pages + 1):
            data = self._gw_get(searchkey, [*base, ("page", str(page))])
            save_raw(self.name, f"search_{search_id}_p{page}.json", json.dumps(data, ensure_ascii=False))
            reached = False
            hits += len(data.get("docs") or [])
            for doc in data.get("docs") or []:
                try:
                    pub = int(doc.get("published") or doc.get("timestamp"))
                except (TypeError, ValueError):
                    out.append(doc)  # let doc_to_rawjob count it
                    continue
                if cursor_ms is not None and pub <= cursor_ms:
                    reached = True
                    break
                out.append(doc)
                newest = pub if newest is None else max(newest, pub)
            meta = data.get("metadata") or {}
            paging = meta.get("paging") or {}
            if (
                reached
                or meta.get("is_end_of_paging")
                or not data.get("docs")
                or int(paging.get("current", page)) >= int(paging.get("last", page))
            ):
                break
        return out, (str(newest) if newest is not None else cursor), hits

    def _known_filters(self, key: str) -> dict[str, set[str]]:
        """Filter ids per filter name for one searchkey. Cached in DATA_DIR/finn_filters.json
        for `filter_check_days`, so the check costs one gateway call per searchkey per period."""
        path = env().data_dir / FILTERS_FILE
        try:
            cache = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(cache, dict):
                cache = {}
        except (OSError, ValueError):
            cache = {}
        entry = cache.get(key)
        if isinstance(entry, dict):
            try:
                age = datetime.now(UTC) - datetime.fromisoformat(entry["fetched_at"])
                if age < timedelta(days=self.filter_check_days):
                    return {name: set(values) for name, values in entry["values"].items()}
            except (KeyError, TypeError, ValueError, AttributeError):
                pass
        data = self._gw_get(
            key, [("client", CLIENT), ("include_results", "false"), ("include_filters", "true")]
        )
        known = _filter_values(data.get("filters") or [])
        cache[key] = {
            "fetched_at": datetime.now(UTC).isoformat(),
            "values": {name: sorted(values) for name, values in known.items()},
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        return known

    def _check_filters(self, searches: dict[str, dict[str, Any]]) -> list[str]:
        """Compare configured filter ids with Finn's filter metadata (see `_known_filters`)."""
        warnings: list[str] = []
        known_by_key: dict[str, dict[str, set[str]]] = {}
        for search_id, search in searches.items():
            key = search.get("searchkey", "SEARCH_ID_JOB_FULLTIME")
            if key not in known_by_key:
                known_by_key[key] = self._known_filters(key)
            known = known_by_key[key]
            for name, values in self._search_params(search).items():
                if name in _NON_FILTER_PARAMS:
                    continue
                if name not in known:
                    warnings.append(f"Ukjent Finn-filter {name} i søk {search_id}")
                    continue
                bad = [v for v in values if v not in known[name]]
                if bad:
                    warnings.append(f"Ukjente Finn-ID-er for {name} i søk {search_id}: {', '.join(bad)}")
        return warnings

    # --- details ---------------------------------------------------------------

    def fetch_details(self, jobs: list[RawJob]) -> list[RawJob]:
        """Fetch ad pages in order, at most `max_details_per_run`. 404/410 marks the ad gone;
        403/429 stops the batch (Finn says no). Jobs not tried keep `detail_attempted = False`."""
        self.detail_message = None
        attempted = 0
        for job in jobs:
            if job.source != self.name or not job.needs_detail:
                continue
            if attempted >= self.max_details_per_run:
                break
            attempted += 1
            job.detail_attempted = True
            try:
                self._fill_detail(job)
            except _HttpFail as e:
                if e.status in (404, 410):
                    job.active = False
                    job.needs_detail = False
                    log.info("finn ad %s is gone (%s)", job.source_id, e.status)
                    continue
                if e.status in (403, 429):
                    self.detail_message = (
                        f"finn.no svarte {e.status} på en annonseside: stoppet detaljhenting til neste kjøring"
                    )
                    log.warning("finn detail backing off after %s", e.status)
                    break
                log.warning("finn detail %s failed: %s", job.source_id, e)
            except Exception as e:  # noqa: BLE001
                log.warning("finn detail %s failed: %s", job.source_id, e)
        return jobs

    def _fill_detail(self, job: RawJob) -> None:
        url = job.url or AD_URL.format(id=job.source_id)
        # No automatic retry: a 429 must stop the batch, and a failed page is retried another day.
        r = self.http.get(url, headers=self._web_headers(), retries=0)
        if r.status_code >= 400:
            raise _HttpFail(r.status_code, "finn.no")
        html = r.text
        job.raw_path = save_raw(self.name, f"{job.source_id}.html", html)
        posting = parse_job_posting(html)
        if not posting or not posting.get("description"):
            raise ValueError("fant ikke JobPosting i JSON-LD")
        job.description_html = posting["description"]
        org = posting.get("hiringOrganization")
        if isinstance(org, dict) and org.get("name"):
            job.company = job.company or org["name"]
            if org.get("url"):
                job.meta["employer_url"] = org["url"]
        if not job.deadline:
            job.deadline = _parse_iso_date(posting.get("validThrough"))
        if posting.get("employmentType"):
            et = posting["employmentType"]
            job.employment_type = ", ".join(et) if isinstance(et, list) else str(et)
        loc = posting.get("jobLocation")
        addr = loc.get("address") if isinstance(loc, dict) else None
        if isinstance(addr, dict):
            job.meta["address"] = {k: v for k, v in addr.items() if not k.startswith("@")}
            job.municipality = job.municipality or addr.get("addressLocality")
        job.application_url = job.application_url or _apply_url(html)
        job.needs_detail = False


__all__ = ["FinnApiSource", "doc_to_rawjob", "parse_job_posting", "device_id", "device_ids"]
