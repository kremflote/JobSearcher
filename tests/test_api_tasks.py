"""Background tasks: POST /api/runs, /api/tasks (ARCHITECTURE §10.1, FRONTEND §3.3)."""

import threading
import time

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from jobsearcher.db.models import Task
from jobsearcher.web import tasks as runner_mod
from jobsearcher.web.app import create_app
from jobsearcher.web.routes import tasks as routes


@pytest.fixture
def client(engine):
    yield TestClient(create_app(dist=None))
    runner_mod.stop_runner()


def wait_for(client, task_id, statuses=("done", "failed", "cancelled"), timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        task = client.get(f"/api/tasks/{task_id}").json()
        if task["status"] in statuses:
            return task
        time.sleep(0.02)
    raise AssertionError(f"task stuck: {task}")


def test_run_lifecycle(client, monkeypatch):
    release = threading.Event()

    def fake_run(ctx):
        ctx.progress(0.5, "Henter fra Finn")
        release.wait(5)
        return "Ferdig: 3 nye jobber"

    monkeypatch.setattr(routes, "make_run_task", lambda trigger="manual": fake_run)
    r = client.post("/api/runs")
    assert r.status_code == 202
    task_id = r.json()["task_id"]

    running = wait_for(client, task_id, statuses=("running",))
    assert running["kind"] == "run"
    assert [t["id"] for t in client.get("/api/tasks?active=true").json()] == [task_id]

    second = client.post("/api/runs")
    assert second.status_code == 409 and second.json()["code"] == "run_active"

    release.set()
    done = wait_for(client, task_id)
    assert done["status"] == "done" and done["progress"] == 1
    assert done["message"] == "Ferdig: 3 nye jobber" and done["result"] is None
    assert done["finished_at"] is not None and done["created_at"].endswith(
        ("+00:00", "Z")
    )
    assert client.get("/api/tasks?active=true").json() == []
    assert client.get("/api/tasks").json()[0]["id"] == task_id


def test_cancel_running_task(client, monkeypatch):
    def fake_run(ctx):
        while not ctx.should_cancel():
            time.sleep(0.01)

    monkeypatch.setattr(routes, "make_run_task", lambda trigger="manual": fake_run)
    task_id = client.post("/api/runs").json()["task_id"]
    wait_for(client, task_id, statuses=("running",))
    r = client.post(f"/api/tasks/{task_id}/cancel")
    assert r.status_code == 200
    assert wait_for(client, task_id)["status"] == "cancelled"


def test_failed_task(client, monkeypatch):
    def fake_run(ctx):
        raise runner_mod.TaskFailed("En kjøring pågår allerede.")

    monkeypatch.setattr(routes, "make_run_task", lambda trigger="manual": fake_run)
    task_id = client.post("/api/runs").json()["task_id"]
    task = wait_for(client, task_id)
    assert (
        task["status"] == "failed" and task["message"] == "En kjøring pågår allerede."
    )


def test_unknown_task_is_404(client):
    assert client.get("/api/tasks/nope").status_code == 404
    assert client.post("/api/tasks/nope/cancel").status_code == 404


def test_startup_marks_leftover_tasks_failed(engine):
    with Session(engine) as s:
        s.add(Task(id="old1", kind="run", status="running"))
        s.add(Task(id="old2", kind="draft", status="queued"))
        s.commit()
    with TestClient(create_app(dist=None)) as client:
        for tid in ("old1", "old2"):
            task = client.get(f"/api/tasks/{tid}").json()
            assert (
                task["status"] == "failed"
                and task["message"] == runner_mod.RESTART_MESSAGE
            )
            assert task["finished_at"] is not None


def test_spa_fallback(engine, tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        "<!doctype html><title>JS</title>", encoding="utf-8"
    )
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    client = TestClient(create_app(dist=dist))
    assert "<title>JS</title>" in client.get("/tracker").text
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/api/health").json()["status"] == "ok"
    r = client.get("/api/nope")
    assert r.status_code == 404 and r.json()["code"] == "not_found"


def test_run_refused_while_lock_held(client):
    from jobsearcher.pipeline.lock import RunLock

    with RunLock():
        r = client.post("/api/runs")
    assert r.status_code == 409 and r.json()["code"] == "run_active"
    assert client.get("/api/tasks").json() == []
