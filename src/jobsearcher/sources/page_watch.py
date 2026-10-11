"""Page watcher for career pages without a feed (ARCHITECTURE §4.4, spike 03).

`collect` fetches one page per company (at most once per `min_hours_between_checks`), turns
the watched part (`selector`, else `<main>`) into Markdown and hashes it. Only when the hash
changed does the extractor agent (a cheap LLM call) list the postings on the page. Each
posting becomes a RawJob; one with its own link gets its ad text from that page in
`fetch_details` (JSON-LD `JobPosting` when the page has it, else the page's main text).

Cursor per company key: `cursor` is JSON `{"hash": ..., "ids": [...], "note": ...}` from the
last successful extraction. A posting that is no longer on the page is emitted as an
inactive RawJob. A failed extraction keeps the old cursor, so the page is tried again next run.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urldefrag, urljoin

import httpx

from jobsearcher.agents.schemas import ExtractResult
from jobsearcher.sources.base import CollectResult, CursorState, RawJob
from jobsearcher.sources.http import HttpClient, RobotsDisallowed, save_raw
from jobsearcher.sources.nav_feed import parse_datetime
from jobsearcher.sources.web import WEB_HEADERS, content_hash, page_markdown, parse_job_posting

log = logging.getLogger(__name__)

MIN_PAGE_CHARS = 200
"""Less text than this: the page is probably rendered by JavaScript, so there is nothing to watch."""
DEFAULT_MAX_DETAILS = 30

Extract = Callable[[str, str, str], ExtractResult]
"""(company, page url, page markdown) → postings. Raises on failure."""


def _default_extract(company: str, url: str, text: str) -> ExtractResult:
    from jobsearcher.agents.extractor import extract_postings

    return extract_postings(company, url, text)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9æøå]+", "-", text.lower()).strip("-")[:80]


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _cursor(state: CursorState | None) -> dict[str, Any]:
    if state is None or not state.cursor:
        return {}
    try:
        data = json.loads(state.cursor)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def posting_to_rawjob(posting: Any, company: dict[str, Any], page_url: str) -> RawJob:
    """One extracted posting → RawJob. A posting with its own link needs its detail page."""
    link = urljoin(page_url, posting.url) if posting.url else None
    if link:
        link = urldefrag(link).url
        if not link.startswith(("http://", "https://")) or link.rstrip("/") == urldefrag(page_url).url.rstrip("/"):
            link = None
    source_id = link or f"{company['key']}#{_slug(posting.title)}"
    job_type = posting.job_type if posting.job_type != "unknown" else company.get("job_type")
    return RawJob(
        source="page_watch",
        source_id=source_id,
        url=link or page_url,
        title=posting.title.strip(),
        company=company.get("company") or company["key"],
        location_text=posting.location,
        deadline=posting.deadline,
        deadline_text=posting.deadline_text,
        application_url=link,
        # Without a page of its own, the summary from the career page is all the text there is.
        description_html=None if link else (posting.summary or posting.title),
        job_type_hint=job_type,
        needs_detail=bool(link),
        meta={"career_page": page_url, **({"page_summary": posting.summary} if posting.summary else {})},
    )


def apply_posting_page(job: RawJob, html: str) -> None:
    """Fill a page-watch job from its own posting page."""
    posting = parse_job_posting(html)
    if posting and posting.get("description"):
        job.description_html = str(posting["description"])
        through = parse_datetime(posting.get("validThrough"))
        if through is not None:
            job.expires_at = through
            if job.deadline is None and not job.deadline_text:
                job.deadline = through.date()
        job.published_at = parse_datetime(posting.get("datePosted")) or job.published_at
        locations = posting.get("jobLocation")
        for loc in locations if isinstance(locations, list) else [locations]:
            address = (loc or {}).get("address") if isinstance(loc, dict) else None
            if isinstance(address, dict) and address.get("addressLocality"):
                job.municipality = job.municipality or str(address["addressLocality"])
                job.location_text = job.location_text or str(address["addressLocality"])
                country = address.get("addressCountry")
                if isinstance(country, dict):
                    country = country.get("name")
                if country and not job.country:
                    job.country = str(country)
                break
    else:
        text = page_markdown(html, job.url or "")
        job.description_html = text if len(text) >= MIN_PAGE_CHARS else None
    job.needs_detail = job.description_html is None


class PageWatchSource:
    name = "page_watch"

    def __init__(self, http: HttpClient, config: dict, extract: Extract | None = None) -> None:
        self.http = http
        self.config = config or {}
        self.companies = [c for c in self.config.get("companies") or [] if c.get("key") and c.get("url")]
        self.min_hours = float(self.config.get("min_hours_between_checks", 20))
        self.max_details = int(self.config.get("max_details_per_run", DEFAULT_MAX_DETAILS))
        self.force = bool(self.config.get("force"))
        self.extract = extract or _default_extract
        self.detail_message: str | None = None

    def _due(self, old: CursorState | None, now: datetime) -> bool:
        if self.force or self.min_hours <= 0 or old is None or old.last_success_at is None:
            return True
        return now - _aware(old.last_success_at) >= timedelta(hours=self.min_hours)

    # --- collect -----------------------------------------------------------------

    def collect(self, state: dict[str, CursorState]) -> CollectResult:
        result = CollectResult()
        now = datetime.now(UTC)
        if not self.companies:
            result.health = "warn"
            result.message = "Karrieresider: ingen sider i sources.yaml"
            return result
        due = [c for c in self.companies if self._due(state.get(c["key"]), now)]
        if not due:
            result.skipped = True
            result.message = f"Karrieresidene ble sjekket for under {self.min_hours:g} t siden"
            return result
        failed: list[str] = []
        changed = 0
        for company in due:
            try:
                if self._check(company, state.get(company["key"]), result):
                    changed += 1
            except Exception as e:  # noqa: BLE001 — one page must not stop the others
                msg = f"{company.get('company') or company['key']}: {e}"
                log.warning("page watch failed: %s", msg)
                failed.append(msg)
        result.found = sum(1 for j in result.jobs if j.active)
        result.errors.extend(failed)
        if failed and len(failed) == len(due):
            result.health = "fail"
            result.message = f"Karrieresider: alle {len(due)} sider feilet"
        elif failed:
            result.health = "warn"
            result.message = f"Karrieresider: {len(failed)} av {len(due)} sider feilet, {changed} endret"
        else:
            result.message = f"Karrieresider: {len(due)} sjekket, {changed} endret, {result.found} utlysninger"
        return result

    def _check(self, company: dict[str, Any], old: CursorState | None, result: CollectResult) -> bool:
        """Check one page. Returns True when it changed and was extracted. Raises on failure."""
        key, url = company["key"], company["url"]
        name = company.get("company") or key
        try:
            r = self.http.get(url, headers=WEB_HEADERS)
        except RobotsDisallowed as e:
            raise RuntimeError("robots.txt tillater ikke siden") from e
        except httpx.HTTPError as e:
            raise RuntimeError(f"{type(e).__name__}: {e}") from e
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code}")
        page_url = str(r.url)
        text = page_markdown(r.text, page_url, company.get("selector"))
        if len(text) < MIN_PAGE_CHARS:
            raise RuntimeError("siden har nesten ingen tekst (lastes den med JavaScript?)")
        digest = content_hash(text)
        prev = _cursor(old)
        if prev.get("hash") == digest:
            # Unchanged: refresh last_success_at, keep the postings from last time.
            result.state[key] = CursorState(cursor=old.cursor if old else None)
            return False
        extracted = self.extract(name, page_url, text)
        raw_path = save_raw(self.name, f"{key}.md", text)
        jobs: dict[str, RawJob] = {}
        for posting in extracted.postings:
            if not posting.title.strip():
                continue
            job = posting_to_rawjob(posting, company, page_url)
            job.raw_path = raw_path
            jobs.setdefault(job.source_id, job)
        ids = list(jobs)
        gone = [i for i in prev.get("ids") or [] if i not in jobs]
        result.jobs.extend(jobs.values())
        result.jobs.extend(RawJob(source=self.name, source_id=i, title="", active=False) for i in gone)
        result.state[key] = CursorState(
            cursor=json.dumps({"hash": digest, "ids": ids, "note": extracted.page_note}, ensure_ascii=False)
        )
        log.info("page changed", extra={"data": {"key": key, "postings": len(ids), "gone": len(gone)}})
        return True

    # --- details -----------------------------------------------------------------

    def fetch_details(self, jobs: list[RawJob]) -> list[RawJob]:
        self.detail_message = None
        fetched = 0
        for job in jobs:
            if job.source != self.name or not job.needs_detail or not job.url:
                continue
            if fetched >= self.max_details:
                self.detail_message = f"maks {self.max_details} utlysningssider per kjøring, resten neste kjøring"
                break
            fetched += 1
            job.detail_attempted = True
            try:
                r = self.http.get(job.url, headers=WEB_HEADERS)
            except (httpx.HTTPError, RobotsDisallowed) as e:
                log.warning("page watch detail %s failed: %s", job.url, e)
                continue
            if r.status_code in (404, 410):
                job.active = False
                continue
            if r.status_code >= 400:
                log.warning("page watch detail %s: HTTP %s", job.url, r.status_code)
                continue
            apply_posting_page(job, r.text)
            if job.description_html:
                job.raw_path = save_raw(self.name, f"detail_{_slug(job.source_id)[-60:]}.html", r.text)
        return jobs


__all__ = ["PageWatchSource", "posting_to_rawjob", "apply_posting_page"]
