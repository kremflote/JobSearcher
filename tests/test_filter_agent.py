"""Filter agent: batching, §5.2 rules in code, rescoring on content change, cost cap, retries."""

from __future__ import annotations

import re
import shutil
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlmodel import select

from jobsearcher.agents.distiller import distill
from jobsearcher.agents.filter import rescore, score_pending
from jobsearcher.config import env
from jobsearcher.context import loader
from jobsearcher.db.models import AgentRun, Evaluation, HardfilterLog, Job, JobContact
from jobsearcher.llm.mock import MockBackend, _filter_batch

FIXTURE_PROFILE = Path(__file__).parent / "fixtures" / "profile"


@pytest.fixture
def profile_dir(tmp_path, monkeypatch, engine) -> Path:
    d = tmp_path / "profile"
    shutil.copytree(FIXTURE_PROFILE, d)
    monkeypatch.setenv("PROFILE_DIR", str(d))
    env.cache_clear()
    return d


@pytest.fixture
def distilled(profile_dir):
    distill(backend=MockBackend())
    return profile_dir


def add_job(session, n: int, text: str | None = "Junior utvikler i et lite team.", **kw) -> Job:
    job = Job(fingerprint=f"fp{n}", title=f"Utvikler {n}", company="Eksempel AS", company_slug="eksempel-as",
              description_clean=text, content_hash=f"hash{n}", **kw)
    session.add(job)
    session.commit()
    return job


def scripted(**overrides_by_id):
    """Mock responder: the default mock result per job, with per-job field overrides."""

    def responder(req):
        out = _filter_batch(req)
        for r in out["results"]:
            r.update(overrides_by_id.get(r["job_id"], {}))
        return out

    return responder


def test_scores_pending_and_records_everything(distilled, session):
    jobs = [add_job(session, i) for i in range(3)]
    backend = MockBackend()
    summary = score_pending(session, backend=backend)
    assert (summary.scored, summary.failed, summary.skipped_reason) == (3, 0, None)

    evs = session.exec(select(Evaluation)).all()
    assert len(evs) == 3
    prompt_version = loader.load_prompt("filter.md").version
    for ev in evs:
        assert ev.profile_hash == loader.derived_profile_hash()
        assert ev.prompt_version == prompt_version
    assert {(ev.job_id, ev.content_hash) for ev in evs} == {(j.id, j.content_hash) for j in jobs}
    run = session.exec(select(AgentRun).where(AgentRun.agent == "filter")).one()
    assert run.status == "ok" and run.job_ids == [j.id for j in jobs] and run.backend == "mock"

    # The ads are wrapped as untrusted data.
    assert len(re.findall(r'<job_ad id="\d+" prefiltered="false">', backend.requests[0].user_content)) == 3

    # Nothing pending now; content change triggers a new evaluation.
    assert score_pending(session, backend=backend).scored == 0
    jobs[1].content_hash = "changed"
    session.add(jobs[1])
    session.commit()
    summary = score_pending(session, backend=backend)
    assert summary.scored == 1
    assert len(session.exec(select(Evaluation).where(Evaluation.job_id == jobs[1].id)).all()) == 2


def test_batches_of_ten(distilled, session):
    for i in range(12):
        add_job(session, i)
    backend = MockBackend()
    progress = []
    summary = score_pending(session, backend=backend, progress=lambda f, m: progress.append(f))
    assert summary.scored == 12
    filter_calls = [r for r in backend.requests if r.agent == "filter"]
    assert len(filter_calls) == 2
    assert progress[0] == 0 and progress[-1] == 1.0


def test_seniority_rules(distilled, session):
    exp = add_job(session, 1)
    exp_finn = add_job(session, 2, prefiltered=True)
    unspec = add_job(session, 3)
    backend = MockBackend(responder=scripted(**{
        str(exp.id): {"seniority": "experienced", "score": 90},
        str(exp_finn.id): {"seniority": "experienced", "score": 88},
        str(unspec.id): {"seniority": "unspecified", "score": 95},
    }))
    score_pending(session, backend=backend)
    for j in (exp, exp_finn, unspec):
        session.refresh(j)
    ev = {e.job_id: e for e in session.exec(select(Evaluation)).all()}

    assert exp.filtered_out is True and exp.seniority == "experienced"
    assert session.exec(select(HardfilterLog).where(HardfilterLog.job_id == exp.id)).one().rule == "llm_seniority"

    assert exp_finn.filtered_out is False
    assert ev[exp_finn.id].seniority == "entry" and ev[exp_finn.id].score == 88

    assert unspec.filtered_out is False
    assert ev[unspec.id].score == 65


def test_fills_missing_job_fields_and_contacts(distilled, session):
    bare = add_job(session, 1)
    known = add_job(session, 2, job_type="permanent", deadline=date(2026, 12, 1), ad_language="no",
                    application_url="https://example.com/feed")
    session.add(JobContact(job_id=known.id, name="Feed Person", source="feed"))
    session.commit()
    llm_fields = {
        "job_type": "trainee",
        "deadline": "2026-11-15",
        "deadline_text": "snarest",
        "application_url": "https://example.com/apply",
        "ad_language": "en",
        "contacts": [{"name": "Kari Eksempel", "role": "Teamleder", "email": "kari@example.com", "phone": None}],
    }
    backend = MockBackend(responder=scripted(**{str(bare.id): llm_fields, str(known.id): llm_fields}))
    score_pending(session, backend=backend)
    session.refresh(bare)
    session.refresh(known)

    assert bare.job_type == "trainee" and bare.deadline == date(2026, 11, 15)
    assert bare.deadline_text == "snarest" and bare.application_url == "https://example.com/apply"
    assert bare.ad_language == "en"
    contacts = session.exec(select(JobContact).where(JobContact.job_id == bare.id)).all()
    assert [(c.name, c.source) for c in contacts] == [("Kari Eksempel", "llm")]

    assert known.job_type == "permanent" and known.deadline == date(2026, 12, 1)
    assert known.application_url == "https://example.com/feed" and known.ad_language == "no"
    contacts = session.exec(select(JobContact).where(JobContact.job_id == known.id)).all()
    assert [c.source for c in contacts] == ["feed"]


def test_retry_on_missing_result(distilled, session):
    a, b = add_job(session, 1), add_job(session, 2)
    calls = []

    def responder(req):
        calls.append(req)
        out = _filter_batch(req)
        if len(calls) == 1:
            out["results"] = out["results"][:1]
        return out

    summary = score_pending(session, backend=MockBackend(responder=responder))
    assert summary.scored == 2 and len(calls) == 2
    assert "Mangler resultat" in calls[1].user_content
    run = session.exec(select(AgentRun).where(AgentRun.agent == "filter")).one()
    assert run.status == "ok"


def test_invalid_output_twice_counts_as_failed(distilled, session):
    add_job(session, 1)
    backend = MockBackend(responder=lambda req: {"results": [{"job_id": "x"}]})
    summary = score_pending(session, backend=backend)
    assert (summary.scored, summary.failed) == (0, 1)
    run = session.exec(select(AgentRun).where(AgentRun.agent == "filter")).one()
    assert run.status == "error" and "Valideringsfeil" in run.error
    assert session.exec(select(Evaluation)).all() == []


def test_cost_cap_stops_scoring(distilled, session):
    add_job(session, 1)
    session.add(AgentRun(agent="writer", backend="mock", model="m", prompt_version="1", cost_usd=30.0,
                         created_at=datetime.now(UTC)))
    session.commit()
    backend = MockBackend()
    summary = score_pending(session, backend=backend)
    assert summary.skipped_reason == "cost_cap" and summary.scored == 0
    assert backend.requests == []


def test_cost_cap_reached_between_batches(distilled, session):
    for i in range(15):
        add_job(session, i)
    backend = MockBackend(cost_usd=30.0)
    summary = score_pending(session, backend=backend)
    assert summary.scored == 10 and summary.skipped_reason == "cost_cap"


def test_cancel_between_batches(distilled, session):
    for i in range(15):
        add_job(session, i)
    calls = iter([False, True])
    summary = score_pending(session, backend=MockBackend(), should_cancel=lambda: next(calls))
    assert summary.scored == 10 and summary.skipped_reason == "cancelled"


def test_distills_first_when_profile_outdated(profile_dir, session):
    add_job(session, 1)
    backend = MockBackend()
    assert loader.derived_outdated()
    summary = score_pending(session, backend=backend)
    assert summary.scored == 1
    assert [r.agent for r in backend.requests] == ["distiller", "filter"]
    assert not loader.derived_outdated()


def test_profile_change_does_not_rescore_automatically_but_rescore_does(distilled, session):
    job = add_job(session, 1)
    backend = MockBackend()
    score_pending(session, backend=backend)
    (distilled / "cv.md").write_text("Ny CV", encoding="utf-8")
    distill(backend=backend)
    assert score_pending(session, backend=backend).scored == 0
    summary = rescore(session, backend=backend)
    assert summary.scored == 1
    evs = session.exec(select(Evaluation).where(Evaluation.job_id == job.id)).all()
    assert len(evs) == 2 and evs[0].profile_hash != evs[1].profile_hash
