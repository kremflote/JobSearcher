"""Tracker endpoints (FRONTEND §5.4, §7; ARCHITECTURE §9.1). Invented data only."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from jobsearcher.db.models import Job, JobContact
from jobsearcher.tracking.status import local_today
from jobsearcher.web.app import create_app


@pytest.fixture
def client(engine):
    return TestClient(create_app(dist=None))


@pytest.fixture
def app_id(client, engine):
    with Session(engine) as s:
        job = Job(
            fingerprint="f",
            title="Utvikler",
            company="Eksempel AS",
            company_slug="eksempel-as",
            deadline=date(2030, 1, 15),
        )
        s.add(job)
        s.flush()
        s.add(JobContact(job_id=job.id, name="Ola Testmann"))
        s.commit()
        job_id = job.id
    return client.put(
        f"/api/jobs/{job_id}/status", json={"status": "interessant"}
    ).json()["application_id"]


def test_list_cards(client, app_id):
    r = client.get("/api/applications")
    assert r.status_code == 200
    [card] = r.json()["items"]
    assert card["id"] == app_id and card["status"] == "interessant"
    assert card["job_title"] == "Utvikler" and card["company"] == "Eksempel AS"
    assert card["deadline"] == "2030-01-15" and card["contact_name"] == "Ola Testmann"
    assert card["allowed_next"] == ["utkast", "sokt", "ikke_aktuell"]
    assert card["previous_status"] is None  # first event came from triage
    assert client.get("/api/applications?status=sokt").json()["items"] == []


def test_patch_sokt_then_undo(client, app_id):
    r = client.patch(
        f"/api/applications/{app_id}", json={"status": "sokt", "comment": "Sendt"}
    )
    assert r.status_code == 200
    card = r.json()
    assert card["status"] == "sokt" and card["previous_status"] == "interessant"
    assert card["applied_at"] is not None
    assert card["follow_up_at"] == (local_today() + timedelta(days=14)).isoformat()
    assert card["allowed_next"] == ["intervju", "avslag", "trukket"]

    events = client.get(f"/api/applications/{app_id}/events").json()
    assert [(e["from_status"], e["to_status"]) for e in events] == [
        ("ny", "interessant"),
        ("interessant", "sokt"),
    ]
    assert events[-1]["comment"] == "Sendt"

    r = client.patch(
        f"/api/applications/{app_id}",
        json={"status": "interessant", "follow_up_at": None},
    )
    card = r.json()
    assert (
        card["status"] == "interessant"
        and card["applied_at"] is None
        and card["follow_up_at"] is None
    )
    assert len(client.get(f"/api/applications/{app_id}/events").json()) == 1


def test_patch_sokt_keeps_given_follow_up(client, app_id):
    card = client.patch(
        f"/api/applications/{app_id}",
        json={"status": "sokt", "follow_up_at": "2030-02-01"},
    ).json()
    assert card["follow_up_at"] == "2030-02-01"


def test_patch_fields_only_when_sent(client, app_id):
    client.patch(
        f"/api/applications/{app_id}", json={"notes": "Ring HR", "next_step": "Case"}
    )
    card = client.patch(
        f"/api/applications/{app_id}", json={"next_step_at": "2030-01-10"}
    ).json()
    assert (
        card["notes"] == "Ring HR"
        and card["next_step"] == "Case"
        and card["next_step_at"] == "2030-01-10"
    )
    card = client.patch(f"/api/applications/{app_id}", json={"notes": None}).json()
    assert card["notes"] is None and card["next_step"] == "Case"


def test_illegal_transition_is_409(client, app_id):
    r = client.patch(f"/api/applications/{app_id}", json={"status": "tilbud"})
    assert r.status_code == 409 and r.json()["code"] == "invalid_transition"
    assert client.get("/api/applications").json()["items"][0]["status"] == "interessant"


def test_unknown_application_is_404(client, engine):
    assert client.patch("/api/applications/999", json={"notes": "x"}).status_code == 404
    assert client.get("/api/applications/999/events").status_code == 404
