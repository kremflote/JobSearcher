"""NavFeedSource against invented fixtures (no network)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from jobsearcher.sources.base import CursorState
from jobsearcher.sources.http import HttpClient
from jobsearcher.sources.nav_feed import NavFeedSource, parse_datetime, parse_deadline


NAV = Path(__file__).parent / "fixtures" / "nav"
BASE = "https://pam-stilling-feed.nav.no"
PAGE1 = "/api/v1/feed/11111111-1111-4111-8111-111111111111"
PAGE2 = "/api/v1/feed/22222222-2222-4222-8222-222222222222"
CONFIG = {"enabled": True, "base_url": BASE, "initial_days_back": 30, "max_pages_per_run": 200}


def _load(name: str) -> str:
    return (NAV / name).read_text(encoding="utf-8")


class FakeNav:
    """Routes requests to fixtures and records them."""

    def __init__(self, routes: dict[str, httpx.Response | list[httpx.Response]]) -> None:
        self.routes = routes
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        resp = self.routes.get(request.url.path)
        if resp is None:
            return httpx.Response(404, json={"title": "Not Found"})
        if isinstance(resp, list):
            return resp.pop(0)
        return resp


def _json(name: str, **headers: str) -> httpx.Response:
    return httpx.Response(200, text=_load(name), headers={"Content-Type": "application/json", **headers})


def _source(fake: FakeNav, token: str = "test-token", **cfg) -> NavFeedSource:
    http = HttpClient(min_interval_s=0, retries=0, backoff_s=0, transport=httpx.MockTransport(fake))
    return NavFeedSource(http, {**CONFIG, **cfg}, token)


def _two_pages() -> FakeNav:
    return FakeNav(
        {
            "/api/v1/feed": _json("feed_page1.json", ETag='"p1"'),
            PAGE2: _json("feed_page2.json", ETag='"p2"'),
            "/api/v1/feedentry/e0000004-0000-4000-8000-000000000004": _json("entry_active.json"),
            "/api/v1/feedentry/e0000005-0000-4000-8000-000000000005": _json("entry_snarest.json"),
        }
    )


def test_first_run_walks_pages_and_keeps_latest_entry_per_ad() -> None:
    fake = _two_pages()
    res = _source(fake).collect({})

    first = fake.requests[0]
    assert first.url.path == "/api/v1/feed"
    assert first.headers["Authorization"] == "Bearer test-token"
    ims = first.headers["If-Modified-Since"]
    assert ims.endswith("GMT")
    assert "If-None-Match" not in first.headers

    assert res.health == "ok", res.message
    ids = [j.source_id for j in res.jobs]
    assert sorted(ids) == sorted(
        ["a0000001-0000-4000-8000-00000000000a", "a0000002-0000-4000-8000-00000000000b", "a0000003-0000-4000-8000-00000000000c"]
    )
    assert res.found == 3
    by_id = {j.source_id: j for j in res.jobs}
    dev = by_id["a0000001-0000-4000-8000-00000000000a"]
    assert dev.title == "Junior utvikler (oppdatert)"  # latest feed item wins
    assert dev.company == "Fjordbyte AS"
    assert dev.municipality == "OSLO"
    assert dev.active and dev.needs_detail and not dev.prefiltered
    assert dev.description_html is None
    assert dev.url == "https://arbeidsplassen.nav.no/stillinger/stilling/a0000001-0000-4000-8000-00000000000a"
    assert dev.meta["detail_url"] == f"{BASE}/api/v1/feedentry/e0000004-0000-4000-8000-000000000004"
    assert dev.raw_path and dev.raw_path.startswith("cache/nav/")

    inactive = by_id["a0000002-0000-4000-8000-00000000000b"]
    assert inactive.active is False and inactive.needs_detail is False

    # End of feed: re-poll the last page with its ETag next time.
    assert res.state["feed"] == CursorState(cursor=PAGE2, etag='"p2"')
    # The malformed item was counted but did not fail the run (1 of 5 = 20 %, not above).
    assert res.errors == ["1 feed-elementer kunne ikke tolkes"]


def test_resume_from_cursor_sends_etag_and_handles_304() -> None:
    fake = FakeNav({PAGE2: httpx.Response(304)})
    res = _source(fake).collect({"feed": CursorState(cursor=PAGE2, etag='"p2"')})
    assert fake.requests[0].headers["If-None-Match"] == '"p2"'
    assert "If-Modified-Since" not in fake.requests[0].headers
    assert res.health == "ok"
    assert res.jobs == []
    assert res.state["feed"] == CursorState(cursor=PAGE2, etag='"p2"')


def test_page_cap_saves_cursor_to_continue() -> None:
    page = json.loads(_load("feed_page1.json"))
    page["items"] = page["items"][:2]  # drop the malformed item
    fake = FakeNav({"/api/v1/feed": httpx.Response(200, json=page)})
    res = _source(fake, max_pages_per_run=1).collect({})
    assert len(fake.requests) == 1
    assert res.health == "ok"
    assert res.state["feed"] == CursorState(cursor=PAGE2, etag=None)
    assert "fortsetter" in (res.message or "")


@pytest.mark.parametrize("status", [401, 403])
def test_auth_error_fails_without_raising(status: int) -> None:
    fake = FakeNav({"/api/v1/feed": httpx.Response(status)})
    prev = {"feed": CursorState()}
    res = _source(fake).collect(prev)
    assert res.health == "fail"
    assert res.message == f"NAV-feeden svarte {status}: token utløpt?"
    assert res.jobs == []


def test_server_error_midway_keeps_progress_as_warning() -> None:
    fake = FakeNav({"/api/v1/feed": _json("feed_page1.json"), PAGE2: httpx.Response(500)})
    res = _source(fake).collect({})
    assert res.health == "warn"
    assert res.message == "NAV-feeden svarte 500"
    assert len(res.jobs) == 2
    assert res.state["feed"] == CursorState(cursor=PAGE2, etag=None)


def test_transport_error_fails() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nede")

    http = HttpClient(min_interval_s=0, retries=0, backoff_s=0, transport=httpx.MockTransport(boom))
    res = NavFeedSource(http, CONFIG, "t").collect({})
    assert res.health == "fail"
    assert "ConnectError" in (res.message or "")


def test_missing_token_fails() -> None:
    fake = FakeNav({})
    res = _source(fake, token="").collect({})
    assert res.health == "fail"
    assert fake.requests == []


def test_empty_first_run_warns() -> None:
    page = json.loads(_load("feed_page2.json"))
    page["items"] = []
    fake = FakeNav({"/api/v1/feed": httpx.Response(200, json=page)})
    res = _source(fake).collect({})
    assert res.health == "warn"


def test_many_parse_failures_warn() -> None:
    page = json.loads(_load("feed_page2.json"))
    page["items"] = [{"id": "x"}, {"id": "y"}, page["items"][0]]
    fake = FakeNav({"/api/v1/feed": httpx.Response(200, json=page)})
    res = _source(fake).collect({})
    assert res.health == "warn"
    assert len(res.jobs) == 1


def test_fetch_details_fills_structured_fields() -> None:
    fake = _two_pages()
    src = _source(fake)
    res = src.collect({})
    wanted = [j for j in res.jobs if j.needs_detail]
    n_before = len(fake.requests)
    jobs = src.fetch_details(wanted)
    assert len(fake.requests) - n_before == 2

    dev = next(j for j in jobs if j.source_id.startswith("a0000001"))
    assert dev.needs_detail is False
    assert dev.description_html.startswith("<p>Vi søker")
    assert dev.org_number == "999999999"
    assert dev.municipality == "OSLO" and dev.county == "OSLO" and dev.country == "NORGE"
    assert dev.location_text == "OSLO, LILLESTRØM"
    assert dev.published_at == datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
    assert dev.expires_at == datetime(2026, 10, 30, 23, 0, tzinfo=UTC)  # naive = Oslo time (CET)
    assert dev.deadline == date(2026, 10, 25) and dev.deadline_text is None
    assert dev.application_url == "https://jobs.fjordbyte.example/123/apply"
    assert dev.employment_type == "Fast"
    assert dev.occupation == ["IT", "Utvikling"]
    assert len(dev.contacts) == 1
    c = dev.contacts[0]
    assert (c.name, c.email, c.role) == ("Kari Eksempel", "kari@fjordbyte.example", "Teamleder – Kontaktperson")
    assert dev.remote == "hybrid"
    for key in ("sector", "extent", "engagementtype", "positioncount", "workLanguage", "remote", "employer_description"):
        assert key in dev.meta, key
    assert dev.meta["occupation"] == ["IT", "Utvikling"]

    trainee = next(j for j in jobs if j.source_id.startswith("a0000003"))
    assert trainee.deadline is None and trainee.deadline_text == "Snarest"
    assert trainee.application_url is None
    assert trainee.contacts == []
    assert trainee.county == "AKERSHUS"


def test_fetch_details_failure_leaves_text_missing() -> None:
    fake = _two_pages()
    src = _source(fake)
    res = src.collect({})
    fake.routes.pop("/api/v1/feedentry/e0000004-0000-4000-8000-000000000004")
    jobs = src.fetch_details([j for j in res.jobs if j.needs_detail])
    dev = next(j for j in jobs if j.source_id.startswith("a0000001"))
    assert dev.description_html is None
    assert dev.needs_detail is True


def test_fetch_details_marks_inactive_entry() -> None:
    fake = _two_pages()
    src = _source(fake)
    res = src.collect({})
    fake.routes["/api/v1/feedentry/e0000004-0000-4000-8000-000000000004"] = httpx.Response(
        200, json={"uuid": "e4", "sistEndret": "2026-10-03T00:00:00Z", "status": "INACTIVE", "ad_content": None}
    )
    jobs = src.fetch_details([j for j in res.jobs if j.source_id.startswith("a0000001")])
    assert jobs[0].active is False
    assert jobs[0].needs_detail is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-11-01", (date(2026, 11, 1), None)),
        ("2026-11-01T00:00:00", (date(2026, 11, 1), None)),
        ("01.11.2026", (date(2026, 11, 1), None)),
        ("Snarest", (None, "Snarest")),
        ("", (None, None)),
        (None, (None, None)),
    ],
)
def test_parse_deadline(raw, expected) -> None:
    assert parse_deadline(raw) == expected


def test_parse_datetime() -> None:
    assert parse_datetime("2026-10-01T08:00:00.000Z") == datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
    assert parse_datetime("2026-07-01T12:00:00") == datetime(2026, 7, 1, 10, 0, tzinfo=UTC)
    assert parse_datetime("tull") is None
