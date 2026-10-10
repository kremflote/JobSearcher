"""Distiller agent with the mock backend and an invented profile."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlmodel import select

from jobsearcher.agents.distiller import DistillError, distill
from jobsearcher.config import env
from jobsearcher.context import loader
from jobsearcher.db.models import AgentRun
from jobsearcher.llm.mock import MockBackend

FIXTURE_PROFILE = Path(__file__).parent / "fixtures" / "profile"


@pytest.fixture
def profile_dir(tmp_path, monkeypatch, engine) -> Path:
    d = tmp_path / "profile"
    shutil.copytree(FIXTURE_PROFILE, d)
    monkeypatch.setenv("PROFILE_DIR", str(d))
    env.cache_clear()
    return d


def test_distill_writes_derived_files_and_manifest(profile_dir, session):
    backend = MockBackend()
    assert distill(backend=backend) is True
    root = env().derived_dir
    for name in ("profile_short.md", "profile_long.md", "voice.md", "manifest.json"):
        assert (root / name).is_file()
    manifest = loader.read_manifest()
    assert manifest["profile_hash"] == loader.profile_hash()
    assert manifest["distiller_prompt_version"] == loader.distiller_prompt_version()
    assert "projects/todo-app.md" in manifest["files"]
    assert "projects/_template.md" not in manifest["files"]
    assert not loader.derived_outdated()

    # The whole profile was sent, wrapped per file; templates excluded.
    req = backend.requests[0]
    assert req.model_tier == "balanced"
    assert '<file path="cv.md">' in req.shared_context
    assert "_template" not in req.shared_context

    runs = session.exec(select(AgentRun)).all()
    assert [(r.agent, r.status) for r in runs] == [("distiller", "ok")]


def test_distill_skips_when_unchanged_and_reruns_on_change(profile_dir):
    backend = MockBackend()
    assert distill(backend=backend) is True
    assert distill(backend=backend) is False
    assert distill(force=True, backend=backend) is True
    (profile_dir / "cv.md").write_text("Ny CV", encoding="utf-8")
    assert loader.derived_outdated()
    assert distill(backend=backend) is True
    assert len(backend.requests) == 3


def test_distill_empty_profile_fails(tmp_path, monkeypatch, engine):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PROFILE_DIR", str(empty))
    env.cache_clear()
    with pytest.raises(DistillError):
        distill(backend=MockBackend())


def test_distill_invalid_output_fails_after_retry(profile_dir, session):
    backend = MockBackend(responder=lambda req: {"profile_short": "bare én"})
    with pytest.raises(DistillError):
        distill(backend=backend)
    assert len(backend.requests) == 2
    assert "ugyldig" in backend.requests[1].user_content
    assert not (env().derived_dir / "manifest.json").exists()
    run = session.exec(select(AgentRun)).one()
    assert run.status == "error"
