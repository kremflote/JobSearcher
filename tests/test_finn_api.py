"""FinnApiSource against invented fixtures (no network)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from jobsearcher.sources import finn_api
from jobsearcher.sources.base import CursorState, RawJob
from jobsearcher.sources.finn_api import FinnApiSource, _oslo_date, device_id, device_ids, parse_job_posting
from jobsearcher.sources.finn_sig import sign_url
from jobsearcher.sources.http import HttpClient

FIX = Path(__file__).parent / "fixtures" / "finn"
PAGE1 = json.loads((FIX / "search_page1.json").read_text(encoding="utf-8"))
PAGE2 = json.loads((FIX / "search_page2.json").read_text(encoding="utf-8"))
FILTERS = json.loads((FIX / "filters_search_id_job_fulltime.json").read_text(encoding="utf-8"))
AD_HTML = (FIX / "ad_page.html").read_text(encoding="utf-8")
EMPTY = {"docs": [], "metadata": {"paging": {"current": 1, "last": 1}, "is_end_of_paging": True}}


class Gateway:
    """Mock transport recording requests; `search` maps page number to response JSON."""

    def __init__(self, search=None, status: int = 200, ad_status: int | dict = 200) -> None:
        self.search = search if search is not None else {1: PAGE1, 2: PAGE2}
        self.status = status
        self.ad_status = ad_status  # one status for all ad pages, or {ad id: status}
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = request.url
        if url.path == "/robots.txt":
            return httpx.Response(404)
        if url.host == "appsgw.finn.no":
            # Reject anything that is not signed exactly like the app does.
            expected = sign_url("GET", str(url), "Search-Quest-JB")
            if request.headers.get("FINN-GW-KEY") != expected:
                return httpx.Response(403)
            if self.status != 200:
                return httpx.Response(self.status)
            if url.params.get("include_results") == "false":
                return httpx.Response(200, json=FILTERS)
            return httpx.Response(200, json=self.search.get(int(url.params.get("page", "1")), EMPTY))
        if url.host == "www.finn.no" and url.path.startswith("/job/ad/"):
            status = self.ad_status
            if isinstance(status, dict):
                status = status.get(url.path.rsplit("/", 1)[-1], 200)
            if status != 200:
                return httpx.Response(status)
            return httpx.Response(200, text=AD_HTML, headers={"content-type": "text/html; charset=utf-8"})
        return httpx.Response(404)

    def search_requests(self) -> list[httpx.Request]:
        return [
            r for r in self.requests
            if r.url.host == "appsgw.finn.no" and r.url.params.get("include_results") != "false"
        ]

    def filter_requests(self) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.params.get("include_results") == "false"]

    def ad_requests(self) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.path.startswith("/job/ad/")]


def make(gw: Gateway, **cfg) -> FinnApiSource:
    http = HttpClient(min_interval_s=0, retries=0, transport=httpx.MockTransport(gw))
    config = {
        "gateway_interval_s": 0,
        "ad_page_interval_s": 0,
        "validate_filters": False,
        "common_params": {"occupation": ["0.23"], "work_experience": ["455", "456"]},
        "searches": {
            "it_oslo": {
                "searchkey": "SEARCH_ID_JOB_FULLTIME",
                "job_type": "permanent",
                "params": {"location": ["1.20001.20061", "1.20001.20003"]},
            }
        },
    }
    config.update(cfg)
    return FinnApiSource(http, config)


def test_first_run_pages_and_maps_fields():
    gw = Gateway()
    res = make(gw).collect({})
    assert res.health == "ok", res
    assert [j.source_id for j in res.jobs] == ["900000003", "900000002", "900000001", "900000000"]
    assert res.found == 4
    assert res.state["it_oslo"].cursor == "1791540000000"
    assert any("1 av 5" in e for e in res.errors)  # the broken doc

    j = res.jobs[0]
    assert j.source == "finn_api"
    assert j.url == "https://www.finn.no/job/ad/900000003"
    assert j.title == "Juniorutvikler - Backend"
    assert j.company == "Fjordbyte AS"
    assert j.municipality == "Oslo" and j.county == "Oslo"
    assert j.published_at == datetime.fromtimestamp(1791540000, UTC)
    assert j.deadline == date(2026, 10, 18)
    assert j.prefiltered and j.needs_detail and j.description_html is None
    assert j.job_type_hint == "permanent"
    assert j.meta["finn_searches"] == ["it_oslo"]
    assert j.meta["extras"] == {"work_experience": ["456"], "education": ["464"]}
    assert j.meta["compensation"] == {"salary_type_id": 447}
    assert res.jobs[1].municipality == "Bærum" and res.jobs[1].county == "Akershus"

    params = gw.search_requests()[0].url.params
    assert params.get_list("location") == ["1.20001.20061", "1.20001.20003"]
    assert params.get_list("work_experience") == ["455", "456"]
    assert params["sort"] == "PUBLISHED_DESC" and params["client"] == "android-finn"
    hdr = gw.search_requests()[0].headers
    assert hdr["FINN-GW-Service"] == "Search-Quest-JB"
    assert hdr["x-nmp-app-version-name"] == "261006-ec709768"
    assert hdr["FINN-App-Installation-Id"] == hdr["Visitor-Id"]


def test_first_run_page_cap():
    gw = Gateway()
    res = make(gw, initial_max_pages=1).collect({})
    assert len(gw.search_requests()) == 1
    assert res.found == 2


def test_cursor_stops_paging():
    gw = Gateway()
    res = make(gw).collect({"it_oslo": CursorState(cursor="1791530000000", etag="e")})
    assert [j.source_id for j in res.jobs] == ["900000003"]
    assert len(gw.search_requests()) == 1
    assert res.state["it_oslo"].cursor == "1791540000000"
    assert res.state["it_oslo"].etag == "e"


def test_nothing_new_keeps_cursor_and_is_ok():
    gw = Gateway()
    res = make(gw).collect({"it_oslo": CursorState(cursor="1791540000000")})
    assert res.jobs == [] and res.health == "ok"
    assert res.state["it_oslo"].cursor == "1791540000000"


def test_same_ad_from_two_searches_is_merged():
    gw = Gateway()
    searches = {
        "it_oslo": {"searchkey": "SEARCH_ID_JOB_FULLTIME", "job_type": "permanent"},
        "trainee": {"searchkey": "SEARCH_ID_JOB_FULLTIME", "job_type": "trainee"},
        "it_norge": {"searchkey": "SEARCH_ID_JOB_FULLTIME", "job_type": "permanent"},
    }
    res = make(gw, searches=searches).collect({})
    assert res.found == 4
    j = res.jobs[0]
    assert j.meta["finn_searches"] == ["it_oslo", "trainee", "it_norge"]
    assert j.job_type_hint == "trainee"
    assert set(res.state) == {"it_oslo", "trainee", "it_norge"}


def test_403_is_fail_and_never_raises():
    gw = Gateway(status=403)
    searches = {"a": {}, "b": {}}
    res = make(gw, searches=searches).collect({"a": CursorState(cursor="1")})
    assert res.health == "fail"
    assert "403" in res.message and "signaturen" in res.message
    assert res.state == {}  # old cursors untouched
    assert len(gw.search_requests()) == 1  # stops after the first 403


def test_500_is_fail():
    res = make(Gateway(status=500)).collect({})
    assert res.health == "fail" and "500" in res.message


def test_zero_hits_is_warn():
    res = make(Gateway(search={})).collect({})
    assert res.health == "warn" and res.found == 0


def test_many_parse_failures_is_warn():
    bad = {"docs": [{"id": str(i), "published": 1} for i in range(3)] + PAGE2["docs"],
           "metadata": {"paging": {"current": 1, "last": 1}}}
    res = make(Gateway(search={1: bad})).collect({})
    assert res.health == "warn"
    assert res.found == 2


def test_filter_check_warns_on_unknown_ids():
    gw = Gateway()
    src = make(gw, validate_filters=True, common_params={"occupation": ["0.23"], "education": ["999"]})
    res = src.collect({})
    assert res.health == "warn"
    assert any("education" in e and "999" in e for e in res.errors)
    assert not any("occupation" in e for e in res.errors)
    assert res.found == 4


def test_filter_check_known_ids_ok():
    src = make(Gateway(), validate_filters=True,
               common_params={"occupation": ["0.23"], "work_experience": ["455", "456"],
                              "education": ["465", "464"], "q": ["graduate"]})
    assert src.collect({}).health == "ok"


def _job(**kw) -> RawJob:
    base = dict(source="finn_api", source_id="900000003", url="https://www.finn.no/job/ad/900000003",
                title="Juniorutvikler", needs_detail=True)
    base.update(kw)
    return RawJob(**base)


def test_fetch_details_fills_fields(data_dir: Path):
    src = make(Gateway())
    other = RawJob(source="nav", source_id="x", title="t", needs_detail=True)
    jobs = src.fetch_details([_job(), other])
    j = jobs[0]
    assert j.description_html.startswith("<p>Vi søker en <strong>juniorutvikler")
    assert j.company == "Fjordbyte AS"
    assert j.application_url == "https://www.finn.no/job-apply/900000003/apply"
    assert j.employment_type == "FULL_TIME"
    assert j.deadline == date(2026, 11, 1)
    assert j.meta["employer_url"] == "https://fjordbyte.example"
    assert j.meta["address"]["postalCode"] == "0150"
    assert not j.needs_detail
    assert (data_dir / j.raw_path).read_text(encoding="utf-8") == AD_HTML
    assert jobs[1].description_html is None and jobs[1].needs_detail


def test_fetch_details_keeps_existing_deadline():
    j = make(Gateway()).fetch_details([_job(deadline=date(2026, 10, 18))])[0]
    assert j.deadline == date(2026, 10, 18)


def test_fetch_details_failure_leaves_none():
    j = make(Gateway(ad_status=500)).fetch_details([_job()])[0]
    assert j.description_html is None and j.needs_detail
    assert j.detail_attempted and j.active


@pytest.mark.parametrize("status", [404, 410])
def test_fetch_details_gone_ad_is_inactive(status):
    j = make(Gateway(ad_status=status)).fetch_details([_job()])[0]
    assert not j.active and not j.needs_detail and j.detail_attempted


def _jobs(n: int) -> list[RawJob]:
    return [_job(source_id=str(i), url=f"https://www.finn.no/job/ad/{i}") for i in range(1, n + 1)]


@pytest.mark.parametrize("status", [403, 429])
def test_fetch_details_stops_when_finn_says_no(status):
    gw = Gateway(ad_status={"2": status})
    src = make(gw)
    jobs = src.fetch_details(_jobs(4))
    assert [r.url.path for r in gw.ad_requests()] == ["/job/ad/1", "/job/ad/2"]  # no retry, no more pages
    assert [j.detail_attempted for j in jobs] == [True, True, False, False]
    assert str(status) in src.detail_message
    assert jobs[0].description_html and jobs[3].needs_detail


def test_fetch_details_cap_per_run():
    gw = Gateway()
    jobs = make(gw, max_details_per_run=2).fetch_details(_jobs(4))
    assert len(gw.ad_requests()) == 2
    assert [j.detail_attempted for j in jobs] == [True, True, False, False]


def test_ad_page_looks_like_the_app_webview():
    gw = Gateway()
    make(gw).fetch_details([_job()])
    hdr = gw.ad_requests()[0].headers
    assert "python-httpx" not in hdr["User-Agent"]
    assert "; wv)" in hdr["User-Agent"] and "Android 14; Pixel 8" in hdr["User-Agent"]
    assert hdr["X-Requested-With"] == "no.finn.android"
    assert hdr["Sec-Fetch-Mode"] == "navigate"
    robots = [r for r in gw.requests if r.url.path == "/robots.txt"][0]
    assert robots.headers["User-Agent"] == hdr["User-Agent"]


def test_gateway_headers_match_the_device():
    gw = Gateway()
    make(gw).collect({})
    hdr = gw.search_requests()[0].headers
    assert hdr["x-nmp-os-version"] == "14" and hdr["x-nmp-device"] == "Pixel 8"
    assert hdr["Ab-Test-Device-Id"] == device_ids()["ab_test_device_id"]
    assert hdr["Ab-Test-Device-Id"] != hdr["Visitor-Id"]


def test_gateway_429_stops_all_searches():
    gw = Gateway(status=429)
    res = make(gw, searches={"a": {}, "b": {}}).collect({})
    assert res.health == "fail" and "429" in res.message
    assert len(gw.search_requests()) == 1


def test_cooldown_skips_recent_run():
    gw = Gateway()
    recent = CursorState(cursor="1", last_success_at=datetime.now(UTC) - timedelta(hours=1))
    res = make(gw).collect({"it_oslo": recent})
    assert res.skipped and "hoppet over" in res.message
    assert gw.requests == []
    assert not make(gw, force=True).collect({"it_oslo": recent}).skipped
    old = CursorState(cursor="1", last_success_at=datetime.now(UTC) - timedelta(hours=4))
    assert not make(gw).collect({"it_oslo": old}).skipped


def test_every_days_skips_search_until_due():
    gw = Gateway(search={})
    searches = {"daily": {}, "weekly": {"every_days": 7}}
    long_ago = datetime.now(UTC) - timedelta(days=4)
    state = {"daily": CursorState(cursor="1", last_success_at=long_ago),
             "weekly": CursorState(cursor="1", last_success_at=long_ago)}
    res = make(gw, searches=searches).collect(state)
    assert set(res.state) == {"daily"}
    assert len(gw.search_requests()) == 1
    state["weekly"].last_success_at = datetime.now(UTC) - timedelta(days=7) + timedelta(hours=1)
    res = make(gw, searches=searches).collect(state)
    assert set(res.state) == {"daily", "weekly"}  # due within the slack


def test_filter_metadata_is_cached(data_dir: Path):
    gw = Gateway()
    cfg = dict(validate_filters=True, common_params={"occupation": ["0.23"]})
    assert make(gw, **cfg).collect({}).health == "ok"
    assert make(gw, **cfg).collect({}).health == "ok"
    assert len(gw.filter_requests()) == 1
    assert (data_dir / "finn_filters.json").exists()
    assert make(gw, filter_check_days=0, **cfg).collect({}).health == "ok"
    assert len(gw.filter_requests()) == 2


def test_parse_job_posting_variants():
    plain = '<script type="application/ld+json">{"@type":"JobPosting","description":"x"}</script>'
    graph = '<script type="application/ld+json">{"@graph":[{"@type":"JobPosting","description":"y"}]}</script>'
    broken = '<script type="application/ld+json">{nope</script>'
    assert parse_job_posting(plain)["description"] == "x"
    assert parse_job_posting(graph)["description"] == "y"
    assert parse_job_posting(broken) is None


def test_device_id_is_stable(data_dir: Path):
    a = device_id()
    assert a == device_id()
    assert json.loads((data_dir / "finn_device.json").read_text())["installation_id"] == a


def test_device_ids_keep_old_installation_id(data_dir: Path):
    old = "1b4e28ba-2fa1-11d2-883f-0016d3cca427"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "finn_device.json").write_text(json.dumps({"installation_id": old}))
    ids = device_ids()
    assert ids["installation_id"] == old
    assert device_ids()["ab_test_device_id"] == ids["ab_test_device_id"]


@pytest.mark.parametrize(
    ("ms", "expected"),
    [
        (1792360799999, date(2026, 10, 18)),  # 23:59:59 CEST
        (1798757999999, date(2026, 12, 31)),  # 23:59:59 CET
        (1798758000000, date(2027, 1, 1)),
    ],
)
def test_oslo_date(ms, expected, monkeypatch):
    dt = datetime.fromtimestamp(ms / 1000, UTC)
    assert _oslo_date(dt) == expected
    # Fallback without tzdata gives the same answer.
    import zoneinfo

    def boom(_):
        raise zoneinfo.ZoneInfoNotFoundError("x")

    monkeypatch.setattr(zoneinfo, "ZoneInfo", boom)
    assert finn_api._oslo_date(dt) == expected
