"""End-to-end pipeline runs with in-memory fake sources (no network, invented data)."""

from __future__ import annotations

import os
import time
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlmodel import select

from jobsearcher.config import env
from jobsearcher.db.models import (
    Application, ApplicationEvent, HardfilterLog, Job, JobContact, JobSource, ScrapeRun, SourceState,
)
from jobsearcher.pipeline import lifecycle as L
from jobsearcher.pipeline.lock import RunLock, RunLockedError
from jobsearcher.pipeline.run import run_pipeline
from jobsearcher.sources.base import CollectResult, CursorState, RawJob


class FakeSource:
    def __init__(self, name, jobs, *, details=None, fail=False, health="ok"):
        self.name = name
        self.jobs = jobs
        self.details = details or {}
        self.fail = fail
        self.health = health
        self.seen_state = None
        self.detail_calls: list[str] = []

    def collect(self, state):
        self.seen_state = state
        if self.fail:
            raise RuntimeError("kilden er nede")
        return CollectResult(jobs=[j.model_copy(deep=True) for j in self.jobs], found=len(self.jobs),
                             state={"main": CursorState(cursor="c2")}, health=self.health)

    def fetch_details(self, jobs):
        for j in jobs:
            self.detail_calls.append(j.source_id)
            if j.source_id in self.details:
                j.description_html = self.details[j.source_id]
                j.needs_detail = False
        return jobs


def finn(sid, title, **kw):
    base = dict(source="finn_api", source_id=sid, title=title, company="Testfirma AS", municipality="Oslo",
                location_text="Oslo", country="Norge", prefiltered=True, needs_detail=True,
                job_type_hint="permanent")
    base.update(kw)
    return RawJob(**base)


def nav(sid, title, **kw):
    base = dict(source="nav", source_id=sid, title=title, company="Navfirma AS", org_number="900000001",
                municipality="OSLO", location_text="Oslo", country="NORGE",
                description_html="<p>Vi søker en nyutdannet utvikler.</p>", occupation=["IT", "Utvikling"])
    base.update(kw)
    return RawJob(**base)


def run(*sources, **kw):
    return run_pipeline("manual", score=False, source_objects=list(sources), **kw)


def test_full_run(engine, session):
    f = FakeSource("finn_api", [
        finn("1", "Junior utvikler"),
        finn("2", "Utvikler", municipality="Bergen", location_text="Bergen"),  # geography: out before detail
        finn("3", "Senior utvikler"),  # prefiltered: seniority title not applied
    ], details={"1": "<p>Du får jobbe med Python.</p>", "3": "<p>Spennende.</p>"})
    n = FakeSource("nav", [
        nav("a", "Utvikler", contacts=[{"name": "Kari Testesen", "role": "Leder"}]),
        nav("b", "Senior utvikler"),
        nav("c", "Utvikler", company="Annenfirma AS", org_number="900000002", description_html="<p>Krav: minst 3 års erfaring med Java.</p>"),
        nav("d", "Sykepleier", occupation=["Helse og sosial"]),
    ])
    summary = run(n, f)
    by = {s.source: s for s in summary.sources}
    assert by["finn_api"].new == 3 and by["finn_api"].filtered_out == 1
    assert by["nav"].new == 4 and by["nav"].filtered_out == 3
    assert sorted(f.detail_calls) == ["1", "3"]  # not "2"
    assert summary.backup_path and os.path.exists(summary.backup_path)

    jobs = {j.title + "/" + (j.company or ""): j for j in session.exec(select(Job))}
    j1 = jobs["Junior utvikler/Testfirma AS"]
    assert j1.description_clean == "Du får jobbe med Python."
    assert j1.ad_text_status == "present" and j1.prefiltered and not j1.filtered_out
    rules = sorted(r.rule for r in session.exec(select(HardfilterLog)))
    assert rules == ["experience_years", "geography", "occupation", "seniority_title"]
    assert session.exec(select(JobContact)).one().source == "feed"
    runs = session.exec(select(ScrapeRun)).all()
    assert {r.source for r in runs} == {"finn_api", "nav"} and all(r.health == "ok" for r in runs)
    state = session.exec(select(SourceState)).all()
    assert {(s.source, s.cursor) for s in state} == {("finn_api", "c2"), ("nav", "c2")}


def test_rerun_updates_and_state_passed(engine, session):
    n = FakeSource("nav", [nav("a", "Utvikler")])
    run(n)
    n.jobs = [nav("a", "Utvikler", description_html="<p>Oppdatert tekst.</p>")]
    s = run(n).sources[0]
    assert n.seen_state["main"].cursor == "c2"
    assert s.new == 0 and s.updated == 1
    assert session.exec(select(Job)).one().description_clean == "Oppdatert tekst."
    s = run(n).sources[0]
    assert s.updated == 0


def test_failing_source_does_not_stop_others_and_keeps_cursor(engine, session):
    bad = FakeSource("finn_api", [], fail=True)
    good = FakeSource("nav", [nav("a", "Utvikler")])
    summary = run(bad, good)
    by = {s.source: s for s in summary.sources}
    assert by["finn_api"].health == "fail" and by["nav"].new == 1
    assert session.exec(select(SourceState).where(SourceState.source == "finn_api")).first() is None


def test_fail_health_does_not_save_cursor(engine, session):
    run(FakeSource("nav", [nav("a", "Utvikler")], health="fail"))
    assert session.exec(select(SourceState)).first() is None
    assert session.exec(select(Job)).one()  # jobs are still stored


def test_inactive_from_source(engine, session):
    n = FakeSource("nav", [nav("a", "Utvikler")])
    run(n)
    n.jobs = [nav("a", "Utvikler", active=False), nav("zz", "Ukjent", active=False)]
    run(n)
    jobs = session.exec(select(Job)).all()
    assert len(jobs) == 1 and jobs[0].active is False


def test_missing_detail_is_retried(engine, session):
    f = FakeSource("finn_api", [finn("1", "Junior utvikler")])
    s = run(f).sources[0]
    assert s.health == "warn"
    job = session.exec(select(Job)).one()
    assert job.ad_text_status == "missing"
    f.jobs = []
    f.details = {"1": "<p>Teksten kom.</p>"}
    run(f)
    session.rollback()  # end the read snapshot taken before the run
    session.refresh(job)
    assert job.description_clean == "Teksten kom." and f.detail_calls == ["1", "1"]


def test_cancel_between_sources(engine):
    a = FakeSource("nav", [nav("a", "Utvikler")])
    b = FakeSource("finn_api", [finn("1", "Utvikler")])
    calls = {"n": 0}

    def cancel():
        calls["n"] += 1
        return a.seen_state is not None

    summary = run(a, b, should_cancel=cancel)
    assert summary.cancelled and [s.source for s in summary.sources] == ["nav"]


def test_score_skipped_without_agent(engine, monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "jobsearcher.agents.filter", None)  # ImportError on import
    summary = run_pipeline("manual", score=True, source_objects=[])
    assert summary.score_skipped_reason


def test_lock(engine):
    with RunLock():
        with pytest.raises(RunLockedError):
            run()
    # Stale lock (dead PID) is taken over.
    env().lock_path.write_text('{"pid": 999999, "started": %f}' % time.time(), encoding="utf-8")
    run()
    # Old lock is stale even if the PID is alive.
    env().lock_path.write_text('{"pid": %d, "started": %f}' % (os.getpid(), time.time() - 3 * 3600), encoding="utf-8")
    run()
    assert not env().lock_path.exists()


def test_lifecycle(engine, session):
    now = datetime(2026, 10, 10, 12, tzinfo=UTC)
    old = Job(fingerprint="a", title="A", company="X", company_slug="x", active=True,
              expires_at=now - timedelta(days=95), last_seen=now - timedelta(days=100))
    keep = Job(fingerprint="b", title="B", company="X", company_slug="x", active=True,
               deadline=date(2026, 10, 1), expires_at=now + timedelta(days=5))
    session.add_all([old, keep])
    session.flush()
    session.add(JobContact(job_id=old.id, name="Kontakt"))
    app = Application(job_id=keep.id, status="interessant")
    session.add(app)
    session.flush()

    assert L.expire_jobs(session, now) == 1 and old.active is False
    assert L.expire_applications(session, now.date()) == 1 and app.status == "utlopt"
    ev = session.exec(select(ApplicationEvent)).one()
    assert (ev.from_status, ev.to_status) == ("interessant", "utlopt")
    assert L.purge_contacts(session, 90, now) == 1

    cache = env().cache_dir
    (cache / "nav" / "2026-08-01").mkdir(parents=True)
    (cache / "nav" / "2026-10-09").mkdir(parents=True)
    assert L.purge_raw_cache(30, now.date()) == 1
    assert (cache / "nav" / "2026-10-09").exists()
