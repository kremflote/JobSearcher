"""Finn via the mobile app gateway (ARCHITECTURE §4.2, spike 04).

Two steps:
1. `collect`: signed `GET /search/{searchkey}` per configured search, newest first, until the
   per-search cursor (highest seen `published`, ms epoch) is reached. No ad text.
2. `fetch_details`: plain GET of the public ad page; the JSON-LD `JobPosting` gives the text.
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
AD_URL = "https://www.finn.no/job/ad/{id}"
SERVICE = "Search-Quest-JB"
CLIENT = "android-finn"
# App identity pinned to the APK the gateway was reverse engineered from (spike 04).
APP_VERSION = "261006-ec709768"
APP_BUILD = "1005273389"
DEVICE_FILE = "finn_device.json"

INITIAL_MAX_PAGES = 3
MAX_PAGES = 10
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


def device_id() -> str:
    """Installation/visitor UUID, generated once and kept in DATA_DIR/finn_device.json."""
    path = env().data_dir / DEVICE_FILE
    try:
        value = json.loads(path.read_text(encoding="utf-8"))["installation_id"]
        return str(uuid.UUID(value))
    except (OSError, ValueError, KeyError, TypeError):
        pass
    value = str(uuid.uuid4())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"installation_id": value}), encoding="utf-8")
    return value


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
        self.initial_max_pages = int(self.config.get("initial_max_pages", INITIAL_MAX_PAGES))
        self.max_pages = int(self.config.get("max_pages", MAX_PAGES))
        self.validate_filters = bool(self.config.get("validate_filters", True))
        self._device_id: str | None = None
        self._session_id = str(uuid.uuid4())

    # --- request helpers -------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        if self._device_id is None:
            self._device_id = device_id()
        return {
            "User-Agent": f"FINN/{self.app_version} (Android 14; FINN-Device-Info: Android, mobile)",
            "FINN-Device-Info": "Android, mobile",
            "FINN-App-Installation-Id": self._device_id,
            "Visitor-Id": self._device_id,
            "Session-Id": self._session_id,
            "Build-Type": "release",
            "VersionCode": self.app_build,
            "X-FINN-API-Version": "5",
            "x-nmp-os-name": "Android",
            "x-nmp-app-brand": "FINN",
            "x-nmp-app-version-name": self.app_version,
            "x-nmp-app-build-number": self.app_build,
            "CMP-Advertising": "0",
            "CMP-Analytics": "0",
            "CMP-Marketing": "0",
            "CMP-Personalisation": "0",
            "FINN-GW-Service": SERVICE,
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

    # --- collect ---------------------------------------------------------------

    def collect(self, state: dict[str, CursorState]) -> CollectResult:
        result = CollectResult()
        jobs: dict[str, RawJob] = {}
        searches: dict[str, dict[str, Any]] = self.config.get("searches") or {}
        total_docs = failed_docs = raw_hits = 0
        warnings: list[str] = []
        fail_msg: str | None = None

        if self.validate_filters:
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
                result.errors.append(msg)
                fail_msg = fail_msg or msg
                if e.status in (401, 403):
                    break  # every search will fail the same way
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

    def _check_filters(self, searches: dict[str, dict[str, Any]]) -> list[str]:
        """Compare configured filter ids with fresh filter metadata (one call per searchkey)."""
        warnings: list[str] = []
        known_by_key: dict[str, dict[str, set[str]]] = {}
        for search_id, search in searches.items():
            key = search.get("searchkey", "SEARCH_ID_JOB_FULLTIME")
            if key not in known_by_key:
                data = self._gw_get(
                    key, [("client", CLIENT), ("include_results", "false"), ("include_filters", "true")]
                )
                known_by_key[key] = _filter_values(data.get("filters") or [])
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
        for job in jobs:
            if job.source != self.name or not job.needs_detail:
                continue
            try:
                self._fill_detail(job)
            except Exception as e:  # noqa: BLE001
                log.warning("finn detail %s failed: %s", job.source_id, e)
        return jobs

    def _fill_detail(self, job: RawJob) -> None:
        url = job.url or AD_URL.format(id=job.source_id)
        r = self.http.get(url, headers={"Accept": "text/html", "Accept-Language": "nb-NO,nb;q=0.9"})
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


__all__ = ["FinnApiSource", "doc_to_rawjob", "parse_job_posting", "device_id"]
