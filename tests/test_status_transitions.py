"""Status transitions (ARCHITECTURE §9.1). Invented data only."""

from datetime import timedelta

import pytest
from sqlmodel import select

from jobsearcher.db.models import Application, ApplicationEvent, Draft, Job
from jobsearcher.tracking.status import (
    TRANSITIONS,
    InvalidTransition,
    allowed_next,
    apply_transition,
    local_today,
    previous_status,
    triage,
)


@pytest.fixture
def job(session):
    j = Job(
        fingerprint="fp1",
        title="Utvikler",
        company="Eksempel AS",
        company_slug="eksempel-as",
    )
    session.add(j)
    session.commit()
    return j


def events(session, app):
    return session.exec(
        select(ApplicationEvent)
        .where(ApplicationEvent.application_id == app.id)
        .order_by(ApplicationEvent.id)
    ).all()


def test_table_matches_architecture():
    assert allowed_next("ny") == ["interessant", "ikke_aktuell"]
    assert allowed_next("tilbud") == ["trukket"]
    for terminal in ("avslag", "trukket", "utlopt"):
        assert allowed_next(terminal) == []
    assert all("utlopt" not in v for v in TRANSITIONS.values())


def test_triage_creates_and_deletes_application(session, job):
    app = triage(session, job, "interessant")
    session.commit()
    assert app.status == "interessant"
    [ev] = events(session, app)
    assert (ev.from_status, ev.to_status) == ("ny", "interessant")
    assert previous_status(session, app) is None

    assert triage(session, job, "ny") is None
    session.commit()
    assert session.exec(select(Application)).all() == []
    assert session.exec(select(ApplicationEvent)).all() == []


def test_triage_refuses_past_triage(session, job):
    app = triage(session, job, "interessant")
    apply_transition(session, app, "sokt")
    with pytest.raises(InvalidTransition):
        triage(session, job, "ikke_aktuell")


def test_triage_back_to_ny_keeps_drafts_safe(session, job):
    app = triage(session, job, "interessant")
    session.add(Draft(application_id=app.id, version=1, content="x", author="user"))
    session.flush()
    with pytest.raises(InvalidTransition):
        triage(session, job, "ny")


def test_sokt_sets_dates_and_undo_clears(session, job):
    app = triage(session, job, "interessant")
    apply_transition(session, app, "sokt", "Sendt via skjema")
    assert app.applied_at is not None and app.applied_at.tzinfo is not None
    assert app.follow_up_at == local_today() + timedelta(days=14)
    assert events(session, app)[-1].comment == "Sendt via skjema"
    assert previous_status(session, app) == "interessant"

    apply_transition(session, app, "interessant")  # undo
    assert app.status == "interessant"
    assert app.applied_at is None and app.follow_up_at is None
    assert len(events(session, app)) == 1


def test_illegal_transition_raises(session, job):
    app = triage(session, job, "interessant")
    with pytest.raises(InvalidTransition):
        apply_transition(session, app, "tilbud")
    with pytest.raises(InvalidTransition):
        apply_transition(session, app, "utlopt")
    with pytest.raises(InvalidTransition):
        apply_transition(session, app, "ny")  # first event is undone by triage


def test_same_status_is_noop(session, job):
    app = triage(session, job, "interessant")
    apply_transition(session, app, "interessant")
    assert len(events(session, app)) == 1
