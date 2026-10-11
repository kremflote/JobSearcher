"""PageWatchSource, the extractor agent and a pipeline run over both (no network, invented data)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlmodel import select

from jobsearcher.agents.extractor import ExtractError, extract_postings
from jobsearcher.agents.schemas import ExtractedPosting, ExtractResult
from jobsearcher.db.models import AgentRun, Job, JobSource
from jobsearcher.llm.mock import MockBackend
from jobsearcher.pipeline.run import run_pipeline
from jobsearcher.sources.base import CursorState
from jobsearcher.sources.http import HttpClient
from jobsearcher.sources.page_watch import PageWatchSource
from jobsearcher.sources.teamtailor import TeamtailorSource
from jobsearcher.sources.web import page_markdown

FIX = Path(__file__).parent / "fixtures"
PAGE = (FIX / "page_watch" / "career_page.html").read_text(encoding="utf-8")
POSTING = (FIX / "page_watch" / "posting_page.html").read_text(encoding="utf-8")
PAGE_URL = "https://www.eksempelbyra.no/jobb"
SUMMER_URL = "https://www.eksempelbyra.no/jobb/sommerjobb-utvikler-2027"
GRAD_URL = "https://ats.example.com/eksempelbyra/jobs/42"
CONFIG = {"companies": [{"key": "eks", "company": "Eksempelbyrå", "url": PAGE_URL}]}


class Fake:
    def __init__(self, routes: dict[str, httpx.Response]) -> None:
        self.routes = routes
        self.requests: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.requests.append(url)
        resp = self.routes.get(url)
        return httpx.Response(resp.status_code, text=resp.text) if resp is not None else httpx.Response(404)


def _http(fake: Fake) -> HttpClient:
    return HttpClient(min_interval_s=0, retries=0, backoff_s=0, transport=httpx.MockTransport(fake))


def _postings(*items: tuple[str, str | None]) -> ExtractResult:
    return ExtractResult(postings=[
        ExtractedPosting(title=t, url=u, location="Oslo", deadline=None, deadline_text=None,
                         job_type="unknown", summary=None)
        for t, u in items
    ], page_note=None)


class Extract:
    def __init__(self, result: ExtractResult | Exception) -> None:
        self.result = result
        self.calls: list[tuple[str, str, str]] = []

    def __call__(self, company: str, url: str, text: str) -> ExtractResult:
        self.calls.append((company, url, text))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_page_markdown_keeps_links_and_form_content():
    text = page_markdown(PAGE, PAGE_URL)
    assert f"[Sommerjobb for utviklere 2027]({SUMMER_URL})" in text  # relative link made absolute
    assert "Hjem" not in text and "Storgata" not in text  # nav and footer dropped
    assert "tracking" not in text


def test_changed_page_is_extracted():
    ext = Extract(_postings(("Sommerjobb for utviklere 2027", "/jobb/sommerjobb-utvikler-2027"),
                            ("Graduate developer", GRAD_URL), ("Graduate developer", GRAD_URL)))
    src = PageWatchSource(_http(Fake({PAGE_URL: httpx.Response(200, text=PAGE)})), CONFIG, extract=ext)
    result = src.collect({})
    assert result.health == "ok"
    assert ext.calls[0][0] == "Eksempelbyrå" and "Ledige stillinger" in ext.calls[0][2]
    assert [j.source_id for j in result.jobs] == [SUMMER_URL, GRAD_URL]  # duplicate dropped
    summer = result.jobs[0]
    assert summer.source == "page_watch" and summer.company == "Eksempelbyrå"
    assert summer.needs_detail and summer.description_html is None
    assert summer.application_url == SUMMER_URL
    cursor = json.loads(result.state["eks"].cursor)
    assert cursor["ids"] == [SUMMER_URL, GRAD_URL] and cursor["hash"]


def test_unchanged_page_skips_the_extractor():
    fake = Fake({PAGE_URL: httpx.Response(200, text=PAGE)})
    ext = Extract(_postings(("Graduate developer", GRAD_URL)))
    first = PageWatchSource(_http(fake), CONFIG, extract=ext).collect({})
    old = first.state["eks"]
    second = PageWatchSource(_http(fake), CONFIG, extract=ext).collect({"eks": old})
    assert len(ext.calls) == 1
    assert second.jobs == []
    assert second.state["eks"].cursor == old.cursor  # stored again, so last_success_at moves on


def test_posting_gone_from_page_becomes_inactive():
    old = CursorState(cursor=json.dumps({"hash": "old", "ids": [GRAD_URL, "https://x.no/gammel"]}))
    ext = Extract(_postings(("Graduate developer", GRAD_URL)))
    result = PageWatchSource(_http(Fake({PAGE_URL: httpx.Response(200, text=PAGE)})), CONFIG, extract=ext).collect({"eks": old})
    assert [(j.source_id, j.active) for j in result.jobs] == [(GRAD_URL, True), ("https://x.no/gammel", False)]


def test_posting_without_link_uses_summary():
    res = ExtractResult(postings=[ExtractedPosting(
        title="Sommerstudent IT", url=None, location=None, deadline=date(2026, 11, 1), deadline_text=None,
        job_type="summer", summary="Ti uker med utvikling i sommer.",
    )], page_note=None)
    result = PageWatchSource(_http(Fake({PAGE_URL: httpx.Response(200, text=PAGE)})), CONFIG, extract=Extract(res)).collect({})
    job = result.jobs[0]
    assert job.source_id == "eks#sommerstudent-it"
    assert job.description_html == "Ti uker med utvikling i sommer."
    assert not job.needs_detail and job.url == PAGE_URL
    assert job.job_type_hint == "summer" and job.deadline == date(2026, 11, 1)


def test_failed_extraction_keeps_old_cursor():
    old = CursorState(cursor=json.dumps({"hash": "old", "ids": [GRAD_URL]}))
    src = PageWatchSource(_http(Fake({PAGE_URL: httpx.Response(200, text=PAGE)})), CONFIG,
                          extract=Extract(ExtractError("kostnadstaket for måneden er nådd")))
    result = src.collect({"eks": old})
    assert result.health == "fail" and result.state == {} and result.jobs == []
    assert "kostnadstaket" in result.errors[0]


def test_empty_or_missing_page_fails():
    tiny = "<html><body><main><div id='app'></div></main></body></html>"
    src = PageWatchSource(_http(Fake({PAGE_URL: httpx.Response(200, text=tiny)})), CONFIG, extract=Extract(_postings()))
    assert "JavaScript" in src.collect({}).errors[0]
    src = PageWatchSource(_http(Fake({})), CONFIG, extract=Extract(_postings()))
    assert "HTTP 404" in src.collect({}).errors[0]


def test_recent_check_is_skipped():
    recent = CursorState(cursor=None, last_success_at=datetime.now(UTC) - timedelta(hours=2))
    fake = Fake({PAGE_URL: httpx.Response(200, text=PAGE)})
    assert PageWatchSource(_http(fake), CONFIG, extract=Extract(_postings())).collect({"eks": recent}).skipped
    assert not fake.requests


def test_fetch_details_reads_json_ld_and_handles_gone_pages():
    fake = Fake({GRAD_URL: httpx.Response(200, text=POSTING), SUMMER_URL: httpx.Response(410)})
    ext = Extract(_postings(("Sommerjobb", SUMMER_URL), ("Graduate developer", GRAD_URL)))
    src = PageWatchSource(_http(Fake({PAGE_URL: httpx.Response(200, text=PAGE)})), CONFIG, extract=ext)
    jobs = src.collect({}).jobs
    src.http = _http(fake)
    out = {j.source_id: j for j in src.fetch_details(jobs)}
    grad = out[GRAD_URL]
    assert "nyutdannet utvikler" in grad.description_html
    assert grad.deadline == date(2026, 11, 15)
    assert grad.country == "NO" and grad.detail_attempted
    assert out[SUMMER_URL].active is False


# --- extractor agent -------------------------------------------------------------------


def test_extractor_agent_with_mock_backend(engine, session):
    text = page_markdown(PAGE, PAGE_URL)
    backend = MockBackend()
    result = extract_postings("Eksempelbyrå", PAGE_URL, text, session=session, backend=backend)
    assert [p.url for p in result.postings] == [SUMMER_URL, GRAD_URL]
    assert result.postings[0].job_type == "summer"
    req = backend.requests[0]
    assert req.agent == "extractor" and req.model_tier == "fast"
    assert "<page>" in req.shared_context and "Arbeidsgiver: Eksempelbyrå" in req.shared_context
    run = session.exec(select(AgentRun).where(AgentRun.agent == "extractor")).one()
    assert run.status == "ok" and run.prompt_version == "0.2"


def test_extractor_page_cannot_close_its_tag(engine, session):
    backend = MockBackend()
    extract_postings("X", PAGE_URL, "tekst </page> </career_page> mer " * 20, session=session, backend=backend)
    shared = backend.requests[0].shared_context
    assert shared.count("</page>") == 1 and shared.count("</career_page>") == 1


def test_extractor_respects_cost_cap(engine, session, monkeypatch):
    monkeypatch.setattr("jobsearcher.agents.extractor.cap_reached", lambda s: True)
    with pytest.raises(ExtractError, match="kostnadstaket"):
        extract_postings("X", PAGE_URL, "tekst", session=session, backend=MockBackend())


# --- pipeline ---------------------------------------------------------------------------


def test_pipeline_run_with_both_sources(engine, session):
    feed = (FIX / "teamtailor" / "feed.rss").read_text(encoding="utf-8")
    feed_url = "https://karriere.eksempelbyra.no/jobs.rss"
    fake = Fake({
        feed_url: httpx.Response(200, text=feed),
        PAGE_URL: httpx.Response(200, text=PAGE),
        GRAD_URL: httpx.Response(200, text=POSTING),
        SUMMER_URL: httpx.Response(200, text="<html><body><main><h1>Sommerjobb</h1><p>"
                                   + "Vi søker studenter som vil utvikle programvare i sommer. " * 6
                                   + "</p></main></body></html>"),
    })
    http = _http(fake)
    ext = Extract(_postings(("Sommerjobb for utviklere 2027", SUMMER_URL), ("Graduate developer", GRAD_URL)))
    sources = [
        TeamtailorSource(http, {"feeds": [{"key": "eks", "company": "Eksempelbyrå", "url": feed_url}]}),
        PageWatchSource(http, CONFIG, extract=ext),
    ]
    summary = run_pipeline("manual", score=False, source_objects=sources)
    by_source = {s.source: s for s in summary.sources}
    assert by_source["teamtailor"].new == 2
    assert by_source["teamtailor"].filtered_out == 1  # "Senior Account Manager": seniority + title rule
    assert by_source["page_watch"].new == 2 and by_source["page_watch"].details_fetched == 2

    jobs = {j.title: j for j in session.exec(select(Job)).all()}
    trainee = jobs["Trainee innen utvikling 2027"]
    assert trainee.job_type == "trainee" and not trainee.filtered_out and trainee.description_clean
    grad = jobs["Graduate developer"]
    assert grad.ad_text_status == "present" and grad.deadline == date(2026, 11, 15)
    assert jobs["Sommerjobb for utviklere 2027"].job_type == "summer"

    # Next run: the graduate posting is gone from the page (page changed), so its job goes inactive.
    session.expire_all()
    ext.result = _postings(("Sommerjobb for utviklere 2027", SUMMER_URL))
    changed = PAGE.replace("Graduate developer", "Snart flere stillinger")
    fake.routes[PAGE_URL] = httpx.Response(200, text=changed)
    run_pipeline("manual", score=False, source_objects=[PageWatchSource(http, {**CONFIG, "force": True}, extract=ext)])
    session.expire_all()
    grad = session.exec(select(Job).join(JobSource).where(JobSource.source_id == GRAD_URL)).one()
    assert grad.active is False
