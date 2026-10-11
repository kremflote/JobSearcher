"""E-mail digest (ARCHITECTURE §11). Invented jobs; SMTP is a fake, nothing is sent."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from jobsearcher.config import load_settings
from jobsearcher.db.models import Application, Evaluation, Job
from jobsearcher.notify import digest as D
from jobsearcher.notify import email as E

NOW = datetime(2026, 10, 12, 6, 0, tzinfo=UTC)
TODAY = date(2026, 10, 12)


def add(session, n, *, score=None, status=None, deadline=None, first_seen=NOW, job_type="permanent", **app):
    job = Job(fingerprint=f"fp{n}", title=f"Utvikler {n}", company=f"Firma {n} AS", company_slug=f"firma-{n}",
              content_hash=f"h{n}", job_type=job_type, deadline=deadline, first_seen=first_seen, location_text="Oslo")
    session.add(job)
    session.commit()
    if score is not None:
        session.add(Evaluation(job_id=job.id, score=score, confidence="high", role_category="backend", job_type=job_type,
                               seniority="entry", tech=[], summary="", key_requirements=[], match_reasons=[], concerns=[],
                               model="mock", prompt_version="0.3", profile_hash="x"))
    if status:
        session.add(Application(job_id=job.id, status=status, **app))
    session.commit()
    return job


def test_sections(session):
    settings = load_settings()
    add(session, 1, score=85)  # new, above threshold
    add(session, 2, score=40)  # new, below threshold
    add(session, 3, score=90, first_seen=NOW - timedelta(days=3))  # old
    add(session, 4, score=90, status="ikke_aktuell")  # triaged
    add(session, 5, score=75, status="interessant", deadline=TODAY + timedelta(days=2), first_seen=NOW - timedelta(days=9))
    add(session, 6, score=75, status="utkast", deadline=TODAY + timedelta(days=10))  # outside 3 days
    add(session, 7, status="sokt", follow_up_at=TODAY - timedelta(days=1))
    add(session, 8, status="avslag", follow_up_at=TODAY)  # closed
    add(session, 9, score=80, job_type="trainee")

    d = D.build_digest(session, settings, since=NOW - timedelta(days=1), source_warnings=["nav feilet: HTTP 401"], on=TODAY)
    assert [j.title for j in d.deadlines] == ["Utvikler 5"]
    assert {t: [j.title for j in js] for t, js in d.new_jobs.items()} == {"permanent": ["Utvikler 1"], "trainee": ["Utvikler 9"]}
    assert [(f.title, f.what) for f in d.follow_ups] == [("Utvikler 7", "Følg opp søknaden")]
    assert d.warnings == ["nav feilet: HTTP 401"]
    assert D.subject(d, TODAY) == "Jobbsøk 12.10.: 1 frist, 2 nye jobber, 1 oppfølging, varsel"
    text = D.render_text(d, "https://jobb.example", TODAY)
    assert "https://jobb.example/jobber/1" in text and "https://jobb.example/tracker?app=" in text
    html = D.render_html(d, "https://jobb.example", TODAY)
    assert "Utvikler 9" in html and "<script" not in html


def test_html_is_escaped(session):
    job = add(session, 1, score=90)
    job.title = "<script>x</script>"
    session.add(job)
    session.commit()
    html = D.render_html(D.build_digest(session, load_settings(), since=NOW - timedelta(days=1), on=TODAY), "https://a", TODAY)
    assert "<script>" not in html and "&lt;script&gt;" in html


class FakeSMTP:
    sent: list = []

    def __init__(self, host, port, timeout):
        self.host = host

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def login(self, user, password):
        self.user = user

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


def test_send_once_then_nothing_new(session, monkeypatch):
    monkeypatch.setenv("GMAIL_ADDRESS", "meg@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "abcd efgh ijkl mnop")
    from jobsearcher.config import env

    env.cache_clear()
    FakeSMTP.sent = []
    real = E.send_email
    monkeypatch.setattr(E, "send_email", lambda *a, **k: real(*a, smtp_factory=FakeSMTP, **k))
    add(session, 1, score=85, first_seen=NOW - timedelta(hours=2))

    assert D.send_digest(session, load_settings(), now=NOW) == "sendt"
    [msg] = FakeSMTP.sent
    assert msg["To"] == "meg@example.com" and "1 nye jobber" in msg["Subject"]
    assert D.last_sent_at() == NOW
    # The same job is not announced again.
    assert D.send_digest(session, load_settings(), now=NOW + timedelta(days=1)) == "ingenting å melde"
    assert len(FakeSMTP.sent) == 1


def test_without_gmail_config_nothing_is_marked(session):
    add(session, 1, score=85)
    result = D.send_digest(session, load_settings(), now=NOW + timedelta(hours=1))
    assert "GMAIL_ADDRESS" in result and D.last_sent_at() is None


def test_dry_run_writes_file(session, tmp_path):
    add(session, 1, score=85)
    out = tmp_path / "d.html"
    assert D.send_digest(session, load_settings(), now=NOW + timedelta(hours=1), dry_run_to=out).startswith("skrevet")
    assert "Utvikler 1" in out.read_text(encoding="utf-8") and D.last_sent_at() is None


@pytest.mark.parametrize("trigger,sent", [("schedule", True), ("manual", False)])
def test_pipeline_sends_digest_on_schedule_only(engine, monkeypatch, trigger, sent):
    from jobsearcher.pipeline import run

    calls = []
    monkeypatch.setattr(D, "send_digest", lambda session, settings, **k: calls.append(1) or "sendt")
    summary = run.run_pipeline(trigger=trigger, score=False, source_objects=[], engine=engine)
    assert (summary.digest == "sendt") is sent and bool(calls) is sent
