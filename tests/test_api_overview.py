"""GET /api/overview (FRONTEND §5.1). Invented data only."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from jobsearcher.db.models import (
    Application,
    Evaluation,
    Job,
    ScrapeRun,
    SettingsOverride,
)
from jobsearcher.tracking.status import local_today
from jobsearcher.web.app import create_app

NOW = datetime.now(UTC)
TODAY = local_today()


@pytest.fixture
def client(engine):
    return TestClient(create_app(dist=None))


def add_job(s, title, *, score=None, status=None, follow_up_at=None, **kw):
    job = Job(
        fingerprint=title,
        title=title,
        company="Eksempel AS",
        company_slug="eksempel-as",
        **kw,
    )
    s.add(job)
    s.flush()
    if score is not None:
        s.add(
            Evaluation(
                job_id=job.id,
                score=score,
                confidence="high",
                role_category="backend",
                job_type=job.job_type,
                seniority="entry",
                summary="",
                model="m",
                prompt_version="0.1",
                profile_hash="h",
            )
        )
    if status:
        s.add(Application(job_id=job.id, status=status, follow_up_at=follow_up_at))
    s.flush()
    return job


def test_empty_database(client):
    r = client.get("/api/overview")
    assert r.status_code == 200
    o = r.json()
    assert o["deadlines"] == [] and o["follow_ups"] == [] and o["last_run_at"] is None
    assert o["new_since_last"] == {"since": None, "counts_by_type": {}, "top": []}
    assert {x["source"] for x in o["sources"]} >= {"finn_api", "nav"}
    assert all(x["health"] is None for x in o["sources"])
    assert o["cost"]["cap_usd"] > 0


def test_overview_blocks(client, engine):
    with Session(engine) as s:
        s.add(
            ScrapeRun(
                trigger="schedule",
                source="finn_api",
                started_at=NOW - timedelta(hours=1),
                finished_at=NOW - timedelta(minutes=58),
                found=10,
                new=2,
            )
        )
        s.add(
            ScrapeRun(
                trigger="schedule",
                source="nav",
                started_at=NOW - timedelta(minutes=57),
                finished_at=NOW - timedelta(minutes=55),
                health="fail",
                errors=["HTTP 401"],
            )
        )
        soon = add_job(
            s,
            "Snart",
            score=70,
            status="interessant",
            deadline=TODAY + timedelta(days=2),
            first_seen=NOW - timedelta(days=5),
        )
        add_job(
            s,
            "Langt unna",
            status="utkast",
            deadline=TODAY + timedelta(days=30),
            first_seen=NOW - timedelta(days=5),
        )
        add_job(
            s,
            "Ny trainee",
            score=90,
            job_type="trainee",
            first_seen=NOW - timedelta(minutes=59),
        )
        add_job(
            s,
            "Ny fast",
            score=50,
            job_type="permanent",
            first_seen=NOW - timedelta(minutes=56),
        )
        add_job(
            s,
            "Ny men skjult",
            score=99,
            filtered_out=True,
            first_seen=NOW - timedelta(minutes=56),
        )
        add_job(
            s,
            "Følg opp",
            status="sokt",
            follow_up_at=TODAY + timedelta(days=3),
            first_seen=NOW - timedelta(days=20),
        )
        add_job(
            s,
            "Følg opp senere",
            status="sokt",
            follow_up_at=TODAY + timedelta(days=12),
            first_seen=NOW - timedelta(days=20),
        )
        add_job(
            s,
            "Avslått",
            status="avslag",
            follow_up_at=TODAY,
            first_seen=NOW - timedelta(days=20),
        )
        s.commit()
        soon_id = soon.id

    o = client.get("/api/overview").json()
    assert [d["id"] for d in o["deadlines"]] == [soon_id]
    assert o["new_since_last"]["counts_by_type"] == {"trainee": 1, "permanent": 1}
    assert [j["title"] for j in o["new_since_last"]["top"]] == ["Ny trainee", "Ny fast"]
    assert o["new_since_last"]["since"] is not None
    assert [c["job_title"] for c in o["follow_ups"]] == ["Følg opp"]
    by_source = {x["source"]: x for x in o["sources"]}
    assert by_source["finn_api"]["health"] == "ok" and by_source["finn_api"]["new"] == 2
    assert (
        by_source["nav"]["health"] == "fail"
        and by_source["nav"]["message"] == "HTTP 401"
    )
    assert o["last_run_at"] is not None


def test_deadline_window_uses_settings_override(client, engine):
    with Session(engine) as s:
        add_job(
            s, "Om ti dager", status="interessant", deadline=TODAY + timedelta(days=10)
        )
        s.add(SettingsOverride(key="thresholds.overview_deadline_days", value=5))
        s.commit()
    assert client.get("/api/overview").json()["deadlines"] == []


def test_logs(client, engine):
    from jobsearcher.db.models import AgentRun, HardfilterLog

    with Session(engine) as s:
        s.add(ScrapeRun(trigger="manual", source="nav", finished_at=NOW, errors=["x"]))
        s.add(AgentRun(agent="filter", backend="mock", model="m", prompt_version="0.1"))
        job = add_job(s, "Forkastet", filtered_out=True)
        s.add(HardfilterLog(job_id=job.id, rule="role_exclude", detail="Selger"))
        s.commit()
    runs = client.get("/api/logs/runs").json()["items"]
    assert runs[0]["source"] == "nav" and runs[0]["errors"] == ["x"]
    assert client.get("/api/logs/agent-runs").json()["items"][0]["agent"] == "filter"
    [d] = client.get("/api/logs/discarded").json()["items"]
    assert d["title"] == "Forkastet" and d["rule"] == "role_exclude"
