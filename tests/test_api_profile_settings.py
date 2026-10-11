"""Phase 4 API: profile files, derived profile, settings and rescore (FRONTEND §5.6–5.7, §7).
Invented profile from tests/fixtures/profile; no network."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jobsearcher.config import env
from jobsearcher.web.app import create_app

FIXTURE_PROFILE = Path(__file__).parent / "fixtures" / "profile"


@pytest.fixture
def profile_dir(tmp_path, monkeypatch) -> Path:
    d = tmp_path / "profile"
    shutil.copytree(FIXTURE_PROFILE, d)
    (d / "projects").mkdir(exist_ok=True)
    (d / "projects" / "_template.md").write_text("---\ntech: []\n---\n# Prosjektnavn\n", encoding="utf-8")
    monkeypatch.setenv("PROFILE_DIR", str(d))
    env.cache_clear()
    return d


@pytest.fixture
def client(engine, profile_dir):
    return TestClient(create_app(dist=None))


def wait_for(client, task_id, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        task = client.get(f"/api/tasks/{task_id}").json()
        if task["status"] in ("done", "failed", "cancelled"):
            return task
        time.sleep(0.02)
    raise AssertionError(f"task stuck: {task}")


# --- Profile ---------------------------------------------------------------------------


def test_tree_lists_profile_files_and_folders(client, profile_dir):
    tree = client.get("/api/profile/files").json()
    paths = [f["path"] for f in tree["files"]]
    assert "profile.yaml" in paths
    assert not any(p.split("/")[-1].startswith("_") for p in paths)
    assert "projects" in tree["folders"]
    assert tree["derived_outdated"] is True and tree["derived_at"] is None


def test_edit_keeps_original_and_new_version(client, profile_dir):
    f = client.get("/api/profile/files/cv.md").json()
    r = client.put("/api/profile/files/cv.md", json={"content": f["content"] + "\nNy linje\n", "base_hash": f["content_hash"]})
    assert r.status_code == 200
    assert (profile_dir / "cv.md").read_text(encoding="utf-8").endswith("Ny linje\n")
    revs = client.get("/api/profile/files/cv.md/revisions").json()
    assert [r["content"] for r in revs] == [f["content"] + "\nNy linje\n", f["content"]]  # newest first

    # A second save from the stale hash is refused.
    stale = client.put("/api/profile/files/cv.md", json={"content": "x", "base_hash": f["content_hash"]})
    assert stale.status_code == 409 and stale.json()["code"] == "conflict"


def test_invalid_yaml_is_refused(client, profile_dir):
    f = client.get("/api/profile/files/profile.yaml").json()
    r = client.put("/api/profile/files/profile.yaml", json={"content": "navn: [uavsluttet\n", "base_hash": f["content_hash"]})
    assert r.status_code == 422 and r.json()["code"] == "invalid_yaml"
    assert (profile_dir / "profile.yaml").read_text(encoding="utf-8") == f["content"]


def test_new_file_from_template(client, profile_dir):
    tpl = client.get("/api/profile/files/projects/_template.md")
    assert tpl.status_code == 200
    r = client.put("/api/profile/files/projects/ny.md", json={"content": tpl.json()["content"], "base_hash": None})
    assert r.status_code == 200 and (profile_dir / "projects" / "ny.md").is_file()
    again = client.put("/api/profile/files/projects/ny.md", json={"content": "x", "base_hash": None})
    assert again.status_code == 409 and again.json()["code"] == "file_exists"
    # Templates are readable but not writable.
    assert client.put("/api/profile/files/projects/_template.md", json={"content": "x", "base_hash": None}).status_code == 400


@pytest.mark.parametrize("path", ["../secret.md", "projects/../../x.md", ".obsidian/a.md", "cv.exe", "C:/x.md"])
def test_paths_outside_profile_are_refused(client, path):
    r = client.put(f"/api/profile/files/{path}", json={"content": "x", "base_hash": None})
    assert r.status_code in (400, 404)
    assert r.status_code == 404 or r.json()["code"] == "invalid_path"


def test_distill_task_and_derived_diff(client, monkeypatch):
    from jobsearcher.agents import distiller
    from jobsearcher.context import loader

    calls = []

    def fake_distill(force=False, **_):
        calls.append(force)
        n = len(calls)
        loader.write_derived(
            {name: f"versjon {n}" for name in loader.DERIVED_FILES},
            {"profile_hash": loader.profile_hash(), "model": "mock", "created_at": "2026-10-11T12:00:00+00:00",
             "distiller_prompt_version": loader.distiller_prompt_version()},
        )
        return True

    monkeypatch.setattr(distiller, "distill", fake_distill)
    for _ in range(2):
        task = wait_for(client, client.post("/api/profile/distill").json()["task_id"])
        assert task["status"] == "done"
    assert calls == [True, True]
    derived = client.get("/api/profile/derived").json()
    assert derived["model"] == "mock"
    short = next(f for f in derived["files"] if f["name"] == "profile_short.md")
    assert short["content"].strip() == "versjon 2" and short["previous_content"].strip() == "versjon 1"
    assert client.get("/api/profile/files").json()["derived_outdated"] is False


# --- Settings --------------------------------------------------------------------------


def _item(settings, key):
    return next(i for i in settings["items"] if i["key"] == key)


def test_settings_override_and_reset(client):
    s = client.get("/api/settings").json()
    item = _item(s, "thresholds.notify_min_score")
    assert item["kind"] == "int" and item["overridden"] is False and item["value"] == item["default"]
    assert _item(s, "search.geography.permanent")["options"]  # modes from locations.yaml

    s = client.patch("/api/settings", json={"values": {"thresholds.notify_min_score": 60, "sources.nav.enabled": False}}).json()
    assert _item(s, "thresholds.notify_min_score")["value"] == 60
    assert _item(s, "sources.nav.enabled")["overridden"] is True

    from jobsearcher.db.repo import current_settings, current_sources

    assert current_settings().thresholds.notify_min_score == 60
    assert current_sources()["nav"]["enabled"] is False

    # null and "same as YAML" both remove the override.
    s = client.patch("/api/settings", json={"values": {"thresholds.notify_min_score": None, "sources.nav.enabled": True}}).json()
    assert _item(s, "thresholds.notify_min_score")["overridden"] is False
    assert _item(s, "sources.nav.enabled")["overridden"] is False


@pytest.mark.parametrize(
    ("key", "value", "code"),
    [
        ("thresholds.notify_min_score", 101, "invalid_setting"),
        ("thresholds.notify_min_score", "70", "invalid_setting"),
        ("schedule.daily_at", "7:00", "invalid_setting"),
        ("llm.backend", "mock", "invalid_setting"),
        ("search.geography.permanent", "månen", "invalid_setting"),
        ("search.repost_after_days", 3, "unknown_setting"),
    ],
)
def test_settings_validation(client, key, value, code):
    r = client.patch("/api/settings", json={"values": {key: value}})
    assert r.status_code == 422 and r.json()["code"] == code


def test_string_lists_are_trimmed(client):
    s = client.patch("/api/settings", json={"values": {"search.role_exclude": [" sikkerhet ", "", "soc", "soc"]}}).json()
    assert _item(s, "search.role_exclude")["value"] == ["sikkerhet", "soc"]


# --- Rescore ---------------------------------------------------------------------------


def test_rescore_estimate_and_task(client, monkeypatch):
    from jobsearcher.agents import filter as filter_agent

    est = client.get("/api/rescore").json()
    assert est == {"stale_jobs": 0, "estimated_cost_usd": 0.0, "cost_per_job_usd": 0.001}

    monkeypatch.setattr(filter_agent, "rescore", lambda session, **_: filter_agent.ScoreSummary(scored=3, failed=1))
    task = wait_for(client, client.post("/api/rescore").json()["task_id"])
    assert task["status"] == "done" and task["message"] == "Ferdig: 3 jobber scoret på nytt (1 feilet)"

    monkeypatch.setattr(filter_agent, "rescore", lambda session, **_: filter_agent.ScoreSummary(skipped_reason="cost_cap"))
    task = wait_for(client, client.post("/api/rescore").json()["task_id"])
    assert task["status"] == "failed" and "Kostnadstaket" in task["message"]
