"""Teamtailor career-site RSS (ARCHITECTURE §4.4, spike 03).

Each company in `sources.yaml` → `teamtailor.feeds` has a public feed at
`https://<career site>/jobs.rss` that lists every open position with its full ad text, so no
detail fetch is needed. One cursor key per feed: `cursor` is JSON `{"ids": [...]}` with the
guids in the last successful read, `etag` the feed's ETag. A guid that drops out of the feed
is emitted as an inactive `RawJob`, so the pipeline deactivates the job.
"""

from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from jobsearcher.sources.base import CollectResult, CursorState, RawJob
from jobsearcher.sources.http import HttpClient, RobotsDisallowed, save_raw
from jobsearcher.sources.web import FEED_HEADERS

log = logging.getLogger(__name__)

TT_NS = "https://teamtailor.com/locations"
NS = {"tt": TT_NS}
NORWAY = {"norway", "norge", "no"}
_REMOTE = {"none": "none", "hybrid": "hybrid", "fully": "full"}


def _text(el: ET.Element | None, path: str) -> str | None:
    if el is None:
        return None
    node = el.find(path, NS)
    if node is None or node.text is None:
        return None
    value = node.text.strip()
    return value or None


def _pub_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def item_to_rawjob(item: ET.Element, feed: dict[str, Any]) -> RawJob:
    """One `<item>` → RawJob. Raises ValueError on an item without guid or title."""
    guid = _text(item, "guid")
    title = _text(item, "title")
    if not guid or not title:
        raise ValueError("item mangler guid eller tittel")
    link = _text(item, "link")
    places: list[str] = []
    countries: list[str] = []
    for loc in item.findall("tt:locations/tt:location", NS):
        place = _text(loc, "tt:city") or _text(loc, "tt:name")
        if place and place not in places:
            places.append(place)
        country = _text(loc, "tt:country")
        if country:
            countries.append(country)
    # A multi-country ad that includes Norway counts as Norwegian (geography rule, §5.3).
    country = next((c for c in countries if c.lower() in NORWAY), countries[0] if countries else None)
    remote_raw = (_text(item, "remoteStatus") or "").lower()
    meta: dict[str, Any] = {"feed": feed["key"]}
    for key, path in (("department", "tt:department"), ("tt_role", "tt:role"), ("remote_status", "remoteStatus")):
        value = _text(item, path)
        if value:
            meta[key] = value
    if _text(item, "company_name"):
        meta["company_name"] = _text(item, "company_name")
    return RawJob(
        source="teamtailor",
        source_id=guid,
        url=link,
        title=title,
        company=feed.get("company") or _text(item, "company_name"),
        location_text=", ".join(places) or None,
        municipality=places[0] if places else None,
        country=country,
        remote=_REMOTE.get(remote_raw),  # type: ignore[arg-type]
        published_at=_pub_date(_text(item, "pubDate")),
        application_url=link,
        description_html=_text(item, "description"),
        job_type_hint=feed.get("job_type"),
        meta=meta,
    )


def parse_feed(xml: str, feed: dict[str, Any]) -> tuple[list[RawJob], int]:
    """Feed XML → (jobs, items that could not be parsed). Raises ET.ParseError on broken XML."""
    root = ET.fromstring(xml)
    jobs: list[RawJob] = []
    failed = 0
    for item in root.iter("item"):
        try:
            jobs.append(item_to_rawjob(item, feed))
        except ValueError as e:
            failed += 1
            log.warning("teamtailor item skipped: %s", e)
    return jobs, failed


def _ids(cursor: str | None) -> list[str]:
    if not cursor:
        return []
    try:
        return list(json.loads(cursor).get("ids") or [])
    except (ValueError, AttributeError):
        return []


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


class TeamtailorSource:
    name = "teamtailor"

    def __init__(self, http: HttpClient, config: dict) -> None:
        self.http = http
        self.config = config or {}
        self.feeds = [f for f in self.config.get("feeds") or [] if f.get("key") and f.get("url")]
        self.min_hours = float(self.config.get("min_hours_between_runs", 3))
        self.force = bool(self.config.get("force"))

    def _due(self, old: CursorState | None, now: datetime) -> bool:
        if self.force or self.min_hours <= 0 or old is None or old.last_success_at is None:
            return True
        return now - _aware(old.last_success_at) >= timedelta(hours=self.min_hours)

    def collect(self, state: dict[str, CursorState]) -> CollectResult:
        result = CollectResult()
        now = datetime.now(UTC)
        if not self.feeds:
            result.health = "warn"
            result.message = "Teamtailor: ingen feeder i sources.yaml"
            return result
        due = [f for f in self.feeds if self._due(state.get(f["key"]), now)]
        if not due:
            result.skipped = True
            result.message = f"Teamtailor hentet for under {self.min_hours:g} t siden"
            return result
        failed: list[str] = []
        unparsed = 0
        for feed in due:
            key = feed["key"]
            old = state.get(key) or CursorState()
            try:
                r = self.http.get(feed["url"], headers=FEED_HEADERS, etag=old.etag)
                if r.status_code == 304:
                    result.state[key] = CursorState(cursor=old.cursor, etag=old.etag)
                    continue
                if r.status_code >= 400:
                    raise ValueError(f"HTTP {r.status_code}")
                jobs, bad = parse_feed(r.text, feed)
            except (httpx.HTTPError, ValueError, ET.ParseError, RobotsDisallowed) as e:
                msg = f"{feed.get('company') or key}: {type(e).__name__}: {e}"
                log.warning("teamtailor feed failed: %s", msg)
                failed.append(msg)
                continue
            unparsed += bad
            raw_path = save_raw(self.name, f"{key}.rss", r.text)
            ids = []
            for job in jobs:
                job.raw_path = raw_path
                ids.append(job.source_id)
            gone = [i for i in _ids(old.cursor) if i not in set(ids)]
            jobs += [RawJob(source=self.name, source_id=i, title="", active=False) for i in gone]
            result.jobs.extend(jobs)
            result.state[key] = CursorState(cursor=json.dumps({"ids": ids}), etag=r.headers.get("ETag"))

        result.found = sum(1 for j in result.jobs if j.active)
        result.errors.extend(failed)
        if unparsed:
            result.errors.append(f"{unparsed} feed-elementer kunne ikke tolkes")
        if failed and len(failed) == len(due):
            result.health = "fail"
            result.message = f"Teamtailor: alle {len(due)} feeder feilet"
        elif failed:
            result.health = "warn"
            result.message = f"Teamtailor: {len(failed)} av {len(due)} feeder feilet"
        else:
            result.message = f"Teamtailor: {result.found} stillinger fra {len(due)} feeder"
        return result

    def fetch_details(self, jobs: list[RawJob]) -> list[RawJob]:
        # The feed carries the full ad text; nothing to fetch.
        return jobs


__all__ = ["TeamtailorSource", "parse_feed", "item_to_rawjob"]
