"""TeamtailorSource against an invented feed (no network)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from jobsearcher.sources.base import CursorState
from jobsearcher.sources.http import HttpClient
from jobsearcher.sources.teamtailor import TeamtailorSource

FEED = (Path(__file__).parent / "fixtures" / "teamtailor" / "feed.rss").read_text(encoding="utf-8")
URL = "https://karriere.eksempelbyra.no/jobs.rss"
CONFIG = {"feeds": [{"key": "eks", "company": "Eksempelbyrå", "url": URL}]}
GUID1 = "aaaaaaaa-0000-4000-8000-000000000001"
GUID2 = "aaaaaaaa-0000-4000-8000-000000000002"


class Fake:
    def __init__(self, routes: dict[str, httpx.Response]) -> None:
        self.routes = routes
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.routes.get(str(request.url).split("?")[0], httpx.Response(404))


def _source(fake: Fake, **cfg) -> TeamtailorSource:
    http = HttpClient(min_interval_s=0, retries=0, backoff_s=0, transport=httpx.MockTransport(fake))
    return TeamtailorSource(http, {**CONFIG, **cfg})


def test_parses_feed():
    fake = Fake({URL: httpx.Response(200, text=FEED, headers={"ETag": '"v1"'})})
    result = _source(fake).collect({})
    assert result.health == "ok"
    assert result.found == 2
    assert "1 feed-elementer kunne ikke tolkes" in result.errors
    trainee = next(j for j in result.jobs if j.source_id == GUID1)
    assert trainee.source == "teamtailor"
    assert trainee.title == "Trainee innen utvikling 2027"
    assert trainee.company == "Eksempelbyrå"
    assert trainee.location_text == "Oslo, Stockholm"
    assert trainee.municipality == "Oslo"
    assert trainee.country == "Norway"  # a Norwegian location wins over the first-listed country
    assert trainee.remote == "hybrid"
    assert trainee.application_url.endswith("/jobs/1001-trainee-innen-utvikling-2027")
    assert "traineeprogrammet" in trainee.description_html
    assert trainee.published_at == datetime(2026, 10, 5, 7, 30, 42, tzinfo=UTC)
    assert trainee.meta["department"] == "Teknologi"
    assert trainee.needs_detail is False and trainee.prefiltered is False
    assert json.loads(result.state["eks"].cursor) == {"ids": [GUID1, GUID2]}
    assert result.state["eks"].etag == '"v1"'
    # robots.txt is asked for (404 → allowed) and the feed request names the tool
    feed_req = next(r for r in fake.requests if r.url.path == "/jobs.rss")
    assert "JobSearcher" in feed_req.headers["User-Agent"]


def test_gone_items_become_inactive_and_etag_is_sent():
    fake = Fake({URL: httpx.Response(200, text=FEED)})
    old = CursorState(cursor=json.dumps({"ids": [GUID1, "old-guid"]}), etag='"v0"')
    result = _source(fake).collect({"eks": old})
    gone = [j for j in result.jobs if not j.active]
    assert [j.source_id for j in gone] == ["old-guid"]
    feed_req = next(r for r in fake.requests if r.url.path == "/jobs.rss")
    assert feed_req.headers["If-None-Match"] == '"v0"'


def test_not_modified_keeps_cursor():
    fake = Fake({URL: httpx.Response(304)})
    old = CursorState(cursor=json.dumps({"ids": [GUID1]}), etag='"v1"')
    result = _source(fake).collect({"eks": old})
    assert result.jobs == []
    assert result.state["eks"].cursor == old.cursor and result.state["eks"].etag == '"v1"'


def test_failing_feed():
    fake = Fake({URL: httpx.Response(500)})
    result = _source(fake).collect({})
    assert result.health == "fail"
    assert result.state == {}
    assert "HTTP 500" in result.errors[0]


def test_one_feed_fails_other_ok():
    other = "https://annen.teamtailor.com/jobs.rss"
    fake = Fake({URL: httpx.Response(200, text=FEED)})
    cfg = {"feeds": CONFIG["feeds"] + [{"key": "annen", "company": "Annen", "url": other}]}
    result = _source(fake, **cfg).collect({})
    assert result.health == "warn"
    assert set(result.state) == {"eks"}


def test_recently_read_feed_is_skipped_unless_forced():
    fake = Fake({URL: httpx.Response(200, text=FEED)})
    recent = CursorState(cursor=None, last_success_at=datetime.now(UTC) - timedelta(hours=1))
    assert _source(fake).collect({"eks": recent}).skipped
    assert not fake.requests
    assert not _source(fake, force=True).collect({"eks": recent}).skipped


def test_registry_builds_phase5_sources():
    from jobsearcher.sources.registry import build_sources

    http = HttpClient(min_interval_s=0, retries=0, backoff_s=0, transport=httpx.MockTransport(Fake({})))
    config = {"teamtailor": {"enabled": True, **CONFIG}, "page_watch": {"enabled": True, "companies": []}}
    assert [s.name for s in build_sources(http, config=config)] == ["teamtailor", "page_watch"]
