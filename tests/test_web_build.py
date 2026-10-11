import os
import subprocess

import pytest

from jobsearcher.web import build


def _touch(path, mtime):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x")
    os.utime(path, (mtime, mtime))


@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setattr(build.shutil, "which", lambda _: "npm")
    _touch(tmp_path / "src" / "main.tsx", 100)
    _touch(tmp_path / "package.json", 100)
    (tmp_path / "node_modules").mkdir()
    return tmp_path


class FakeRun:
    def __init__(self, codes=None):
        self.calls = []
        self.codes = codes or {}

    def __call__(self, cmd, cwd):
        self.calls.append(cmd[1:])
        return subprocess.CompletedProcess(cmd, self.codes.get(cmd[-1], 0))


def test_missing_dist_builds(web):
    run = FakeRun()
    assert build.ensure_built(web, run) is True
    assert run.calls == [["run", "build"]]


def test_fresh_dist_skips(web):
    _touch(web / "dist" / "index.html", 200)
    run = FakeRun()
    assert build.ensure_built(web, run) is False
    assert run.calls == []


def test_newer_source_rebuilds(web):
    _touch(web / "dist" / "index.html", 200)
    _touch(web / "src" / "features" / "Page.tsx", 300)
    run = FakeRun()
    assert build.ensure_built(web, run) is True


def test_newer_unrelated_file_is_ignored(web):
    _touch(web / "dist" / "index.html", 200)
    _touch(web / "e2e" / "smoke.spec.ts", 300)
    assert build.is_stale(web) is False


def test_installs_dependencies_first(web):
    (web / "node_modules").rmdir()
    run = FakeRun()
    assert build.ensure_built(web, run) is True
    assert run.calls == [["ci"], ["run", "build"]]


def test_failed_build_does_not_raise(web):
    run = FakeRun(codes={"build": 1})
    assert build.ensure_built(web, run) is False


def test_no_npm_skips(web, monkeypatch):
    monkeypatch.setattr(build.shutil, "which", lambda _: None)
    run = FakeRun()
    assert build.ensure_built(web, run) is False
    assert run.calls == []


def test_no_sources_skips(tmp_path):
    run = FakeRun()
    assert build.ensure_built(tmp_path, run) is False
    assert run.calls == []
