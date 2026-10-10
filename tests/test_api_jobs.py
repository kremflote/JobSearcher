"""GET /api/jobs, /api/jobs/{id}, PUT /api/jobs/{id}/status. Invented data only."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from jobsearcher.db.models import (
    Application,
    Evaluation,
    Job,
    JobContact,
    JobSource,
    ScrapeRun,
)
from jobsearcher.tracking.status import local_today
from jobsearcher.web.app import create_app

NOW = datetime.now(UTC)
TODAY = local_today()


def add_job(
    s: Session, title: str, *, score=None, role="backend", source="finn_api", **kw
) -> Job:
    kw.setdefault("company", "Eksempel AS")
    kw.setdefault("company_slug", "eksempel-as")
    job = Job(fingerprint=title, title=title, **kw)
    s.add(job)
    s.flush()
    s.add(
        JobSource(
            job_id=job.id,
            source=source,
            source_id=f"{source}-{job.id}",
            url="https://example.test",
        )
    )
    if score is not None:
        s.add(
            Evaluation(
                job_id=job.id,
                score=score,
                confidence="high",
                role_category=role,
                job_type=job.job_type,
                seniority="entry",
                summary="Kort",
                model="m",
                prompt_version="0.1",
                profile_hash="h",
            )
        )
    s.flush()
    return job


@pytest.fixture
def client(engine):
    return TestClient(create_app(dist=None))


@pytest.fixture
def seeded(engine):
    with Session(engine, expire_on_commit=False) as s:
        s.add(
            ScrapeRun(
                trigger="schedule",
                source="finn_api",
                started_at=NOW - timedelta(days=1, minutes=5),
                finished_at=NOW - timedelta(days=1),
            )
        )
        s.add(
            ScrapeRun(
                trigger="schedule",
                source="finn_api",
                started_at=NOW - timedelta(hours=1),
                finished_at=NOW - timedelta(minutes=50),
            )
        )
        jobs = {
            "a": add_job(
                s,
                "Backendutvikler",
                score=80,
                deadline=TODAY + timedelta(days=3),
                first_seen=NOW - timedelta(minutes=55),
                description_clean="Python og Django",
            ),
            "b": add_job(
                s,
                "Frontendutvikler",
                score=60,
                role="frontend",
                deadline=TODAY + timedelta(days=10),
                job_type="trainee",
                source="nav",
                first_seen=NOW - timedelta(days=2),
            ),
            "c": add_job(s, "Uscoret", first_seen=NOW - timedelta(days=3)),
            "hidden": add_job(s, "Senior", score=90, filtered_out=True),
            "expired": add_job(
                s, "Utløpt", score=70, deadline=TODAY - timedelta(days=1)
            ),
            "inactive": add_job(s, "Borte", score=70, active=False),
        }
        s.add(
            JobContact(
                job_id=jobs["a"].id, name="Kari Testesen", email="kari@example.test"
            )
        )
        s.commit()
        return {k: v.id for k, v in jobs.items()}


def ids(r):
    return [i["id"] for i in r.json()["items"]]


def test_list_defaults(client, seeded):
    r = client.get("/api/jobs")
    assert r.status_code == 200
    body = r.json()
    # Deadline first (nulls last), filtered_out/expired/inactive untriaged hidden.
    assert ids(r) == [seeded["a"], seeded["b"], seeded["c"]]
    assert body["total"] == 3 and body["next_cursor"] is None
    a = body["items"][0]
    assert a["status"] == "ny" and a["score"] == 80 and a["role_category"] == "backend"
    assert (
        a["sources"] == ["finn_api"] and a["is_new"] is True and a["reposted"] is False
    )
    assert body["items"][1]["is_new"] is False
    assert (
        body["items"][2]["score"] is None and body["items"][2]["role_category"] is None
    )
    assert a["first_seen"].endswith(("+00:00", "Z"))


def test_filters_and_sorting(client, seeded):
    assert ids(client.get("/api/jobs?type=trainee")) == [seeded["b"]]
    assert ids(client.get("/api/jobs?min_score=70")) == [seeded["a"]]
    assert ids(client.get("/api/jobs?source=nav")) == [seeded["b"]]
    assert ids(client.get("/api/jobs?role=frontend")) == [seeded["b"]]
    assert ids(client.get("/api/jobs?q=django")) == [seeded["a"]]
    before = (TODAY + timedelta(days=5)).isoformat()
    assert ids(client.get(f"/api/jobs?deadline_before={before}")) == [seeded["a"]]
    assert ids(client.get("/api/jobs?sort=score")) == [
        seeded["a"],
        seeded["b"],
        seeded["c"],
    ]
    assert ids(client.get("/api/jobs?sort=newest")) == [
        seeded["a"],
        seeded["b"],
        seeded["c"],
    ]


def test_cursor_paging(client, seeded):
    r1 = client.get("/api/jobs?limit=2")
    assert ids(r1) == [seeded["a"], seeded["b"]] and r1.json()["total"] == 3
    cursor = r1.json()["next_cursor"]
    r2 = client.get("/api/jobs", params={"limit": 2, "cursor": cursor})
    assert ids(r2) == [seeded["c"]] and r2.json()["next_cursor"] is None
    assert client.get("/api/jobs?cursor=bogus!").status_code == 400


def test_triage_and_status_filter(client, seeded, engine):
    a = seeded["a"]
    r = client.put(f"/api/jobs/{a}/status", json={"status": "interessant"})
    assert r.status_code == 200
    app_id = r.json()["application_id"]
    assert r.json() == {"job_id": a, "status": "interessant", "application_id": app_id}
    assert ids(client.get("/api/jobs?status=interessant")) == [a]
    assert seeded["a"] not in ids(client.get("/api/jobs?status=ny"))

    r = client.put(f"/api/jobs/{a}/status", json={"status": "ny"})
    assert r.json()["application_id"] is None
    with Session(engine) as s:
        assert s.exec(select(Application)).all() == []


def test_triaged_expired_job_stays_visible(client, seeded):
    client.put(f"/api/jobs/{seeded['expired']}/status", json={"status": "ikke_aktuell"})
    assert seeded["expired"] in ids(client.get("/api/jobs"))


def test_triage_past_tracker_status_is_409(client, seeded):
    a = seeded["a"]
    app_id = client.put(f"/api/jobs/{a}/status", json={"status": "interessant"}).json()[
        "application_id"
    ]
    client.patch(f"/api/applications/{app_id}", json={"status": "sokt"})
    r = client.put(f"/api/jobs/{a}/status", json={"status": "ikke_aktuell"})
    assert r.status_code == 409 and r.json()["code"] == "invalid_transition"


def test_detail(client, seeded):
    r = client.get(f"/api/jobs/{seeded['a']}")
    assert r.status_code == 200
    d = r.json()
    assert d["evaluation"]["score"] == 80
    assert d["contacts"][0]["name"] == "Kari Testesen"
    assert d["source_refs"][0]["source"] == "finn_api"
    assert d["description"] == "Python og Django"
    assert d["application"] is None and d["company_note"] is None
    client.put(f"/api/jobs/{seeded['a']}/status", json={"status": "interessant"})
    app = client.get(f"/api/jobs/{seeded['a']}").json()["application"]
    assert app["status"] == "interessant" and app["latest_draft_id"] is None


def test_unknown_job_is_404(client, engine):
    r = client.get("/api/jobs/999")
    assert r.status_code == 404 and r.json()["code"] == "not_found"
    assert (
        client.put("/api/jobs/999/status", json={"status": "interessant"}).status_code
        == 404
    )
