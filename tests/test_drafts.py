"""Phase 3: researcher, writer, reviser, the drafts API and .docx export (ARCHITECTURE §6.4,
§7.3–7.4, §9.1; FRONTEND §7)."""

from __future__ import annotations

import io
import shutil
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from jobsearcher.agents import writer as writer_mod
from jobsearcher.agents.distiller import distill
from jobsearcher.agents.writer import clean_letter, write_first_draft
from jobsearcher.config import env
from jobsearcher.context.projects import rank_projects
from jobsearcher.db.models import (
    AgentRun,
    Application,
    ApplicationEvent,
    Company,
    Draft,
    DraftMessage,
    Evaluation,
    Job,
)
from jobsearcher.export.docx import filename, sender_from_profile
from jobsearcher.llm.mock import MockBackend, _from_schema
from jobsearcher.llm.base import output_json_schema
from jobsearcher.tracking import drafts
from jobsearcher.web import tasks as runner_mod
from jobsearcher.web.app import create_app

FIXTURE_PROFILE = Path(__file__).parent / "fixtures" / "profile"

NOTE = {
    "what_they_do": "Lager regnskapsprogram for små bedrifter.",
    "size_and_locations": "40 ansatte i Oslo.",
    "tech_and_engineering": "Python og React.",
    "recent_news": ["2026-05: Lanserte ny app"],
    "culture_and_values": None,
    "hooks_for_letter": ["Ny app for timeføring"],
    "sources": ["https://eksempel.no/om-oss"],
}


@pytest.fixture
def profile(tmp_path, monkeypatch, engine) -> Path:
    d = tmp_path / "profile"
    shutil.copytree(FIXTURE_PROFILE, d)
    (d / "projects" / "kotlin-app.md").write_text(
        "---\ntech: [Kotlin]\ncategories: [mobile]\ntype: personlig\n---\n# Kotlin-app (oppdiktet)\n\nEn app.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PROFILE_DIR", str(d))
    env.cache_clear()
    distill(backend=MockBackend())
    return d


def responder(note=NOTE, fail_research=False):
    """Mock outputs per agent; the researcher can be made to fail."""
    from jobsearcher.llm.mock import BUILTIN

    def respond(req):
        name = req.output_schema.__name__
        if name == "CompanyNote":
            if fail_research:
                return "ikke json"
            return note
        if name in BUILTIN:
            return BUILTIN[name](req)
        return _from_schema(output_json_schema(req.output_schema))

    return respond


def add_job(session: Session, *, meta=None, ad_language="no", evaluation=True) -> Job:
    job = Job(
        fingerprint="fp1",
        title="Junior utvikler",
        company="Eksempel AS",
        company_slug="eksempel-as",
        description_clean="Vi søker en junior utvikler med Python og FastAPI.",
        content_hash="h1",
        ad_language=ad_language,
        meta=meta or {},
    )
    session.add(job)
    session.commit()
    if evaluation:
        session.add(
            Evaluation(
                job_id=job.id, score=80, confidence="high", role_category="backend", job_type="permanent",
                seniority="entry", tech=["Python", "fastapi"], summary="Backend-jobb.",
                key_requirements=["Python"], match_reasons=["Python-prosjekter"], concerns=["Ingen erfaring"],
                model="mock", prompt_version="0.3", profile_hash="x",
            )
        )
        session.commit()
    return job


# --- Project selection (§6.4) -------------------------------------------------------------


def test_projects_ranked_by_tech_role_and_highlight(profile):
    ranked = rank_projects(["python", "FastAPI"], "backend")
    assert [p.title for p in ranked] == ["Todo-app (oppdiktet)", "Kotlin-app (oppdiktet)"]
    assert ranked[0].score == 3 * 2 + 2 + 2  # two shared techs, category, highlight
    assert ranked[1].score == 1  # personal project, nothing in common
    # aliases: "kotlin" matches, "py" is an alias for python
    assert rank_projects(["kotlin"], "mobile")[0].title == "Kotlin-app (oppdiktet)"
    assert rank_projects(["py"], None)[0].score == 3 + 2


# --- Writer and researcher -----------------------------------------------------------------


def test_first_draft_creates_application_note_and_version(profile, session):
    job = add_job(session, meta={"employer_homepage": "https://eksempel.no"})
    backend = MockBackend(responder())
    out = write_first_draft(job.id, backend=backend)

    with Session(session.get_bind()) as s:
        app = s.get(Application, out.application_id)
        assert app.status == "utkast"
        events = s.exec(select(ApplicationEvent).where(ApplicationEvent.application_id == app.id)).all()
        assert [(e.from_status, e.to_status) for e in events] == [("ny", "interessant"), ("interessant", "utkast")]
        draft = s.get(Draft, out.draft_id)
        assert (draft.version, draft.author, draft.claims_to_verify) == (1, "agent", ["Mock-påstand"])
        assert "mock-utkast" in draft.content
        [msg] = s.exec(select(DraftMessage)).all()
        assert (msg.role, msg.draft_id) == ("agent", draft.id) and msg.text.startswith("Første utkast.")
        company = s.get(Company, "eksempel-as")
        assert company.note_quality == "full" and company.homepage == "https://eksempel.no"
        note = (env().data_dir / company.note_path).read_text(encoding="utf-8")
        assert "## Kroker for brevet\n- Ny app for timeføring" in note
        runs = s.exec(select(AgentRun).order_by(AgentRun.id)).all()
        assert [(r.agent, r.application_id) for r in runs if r.agent != "distiller"] == [
            ("researcher", app.id), ("writer", app.id)
        ]

    # the writer saw the ad, the note, the best project and the evaluation
    writer_req = backend.requests[-1]
    content = writer_req.full_user_content()
    for expected in ("<job_ad>", "Ny app for timeføring", 'title="Todo-app (oppdiktet)"', "Ingen erfaring",
                     "<voice>", "<profile_long>", "norsk (bokmål)"):
        assert expected in content
    assert writer_req.model_tier == "best"


def test_note_is_cached_and_research_failure_falls_back(profile, session):
    job = add_job(session, meta={"employer_description": "Eksempel AS lager ting."})
    backend = MockBackend(responder(fail_research=True))
    write_first_draft(job.id, backend=backend)
    with Session(session.get_bind()) as s:
        company = s.get(Company, "eksempel-as")
        assert company.note_quality == "limited"
        note = (env().data_dir / company.note_path).read_text(encoding="utf-8")
        assert "Eksempel AS lager ting." in note
        failed = s.exec(select(AgentRun).where(AgentRun.agent == "researcher")).one()
        assert failed.status == "error"

    # A full note younger than 90 days is reused without a new research call.
    with Session(session.get_bind()) as s:
        company = s.get(Company, "eksempel-as")
        company.note_quality = "full"
        s.add(company)
        for msg in s.exec(select(DraftMessage)).all():
            s.delete(msg)
        s.flush()
        for d in s.exec(select(Draft)).all():
            s.delete(d)
        s.commit()
    backend = MockBackend(responder())
    write_first_draft(job.id, backend=backend)
    assert [r.output_schema.__name__ for r in backend.requests] == ["DraftResult"]


def test_english_ad_gets_english_instruction(profile, session):
    job = add_job(session, ad_language="en")
    backend = MockBackend(responder())
    out = write_first_draft(job.id, backend=backend)
    with Session(session.get_bind()) as s:
        assert s.get(Draft, out.draft_id).content.startswith("Dear hiring team")


def test_draft_refused_when_cost_cap_reached(profile, session):
    job = add_job(session)
    session.add(AgentRun(agent="filter", backend="openrouter", model="m", prompt_version="1", cost_usd=50.0,
                         status="ok"))
    session.commit()
    with pytest.raises(writer_mod.DraftError, match="Kostnadstaket"):
        write_first_draft(job.id, backend=MockBackend(responder()))
    assert session.exec(select(Application)).first() is None


# --- Versions (autosave) -------------------------------------------------------------------


def _app_with_draft(session: Session) -> tuple[Application, Draft]:
    job = add_job(session, evaluation=False)
    app = Application(job_id=job.id, status="utkast")
    session.add(app)
    session.flush()
    draft = drafts.add_draft(session, app.id, "Versjon 1", author="agent", claims_to_verify=["A"])
    session.commit()
    return app, draft


def test_autosave_updates_young_user_version_in_place(session):
    app, v1 = _app_with_draft(session)
    v2 = drafts.save_user_version(session, app.id, "Brukertekst")
    assert (v2.version, v2.author, v2.claims_to_verify) == (2, "user", ["A"])
    again = drafts.save_user_version(session, app.id, "Brukertekst 2")
    assert again.id == v2.id and again.content == "Brukertekst 2"
    later = drafts.save_user_version(session, app.id, "Senere", now=datetime.now(UTC) + timedelta(minutes=11))
    assert later.version == 3
    with pytest.raises(drafts.DraftNotFound):
        drafts.save_user_version(session, app.id, "x", base_draft_id=999)


# --- API ----------------------------------------------------------------------------------


@pytest.fixture
def client(profile, monkeypatch):
    backend = MockBackend(responder())
    monkeypatch.setattr(writer_mod, "get_backend", lambda name=None: backend)
    yield TestClient(create_app(dist=None))
    runner_mod.stop_runner()


def wait_for(client, task_id, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        task = client.get(f"/api/tasks/{task_id}").json()
        if task["status"] in ("done", "failed", "cancelled"):
            return task
        time.sleep(0.02)
    raise AssertionError(f"task stuck: {task}")


def test_api_draft_flow(client, session):
    job = add_job(session)
    r = client.post(f"/api/jobs/{job.id}/draft")
    assert r.status_code == 202
    task = wait_for(client, r.json()["task_id"])
    assert task["status"] == "done" and task["kind"] == "draft", task
    assert task["message"] == "Ferdig: versjon 1"
    app_id, v1 = task["result"]["application_id"], task["result"]["draft_id"]

    again = client.post(f"/api/jobs/{job.id}/draft")
    assert again.status_code == 409 and again.json()["code"] == "draft_exists"

    assert client.get(f"/api/jobs/{job.id}").json()["application"] == {
        "id": app_id, "status": "utkast", "latest_draft_id": v1
    }
    [card] = client.get("/api/applications").json()["items"]
    assert card["latest_draft_id"] == v1

    versions = client.get(f"/api/applications/{app_id}/drafts").json()
    assert [(v["version"], v["author"]) for v in versions] == [(1, "agent")]
    draft = client.get(f"/api/drafts/{v1}").json()
    assert draft["claims_to_verify"] == ["Mock-påstand"]

    # autosave
    saved = client.post(f"/api/applications/{app_id}/drafts", json={"content": "Min tekst", "base_draft_id": v1})
    assert saved.status_code == 201 and saved.json()["version"] == 2
    assert saved.json()["claims_to_verify"] == ["Mock-påstand"]
    in_place = client.post(f"/api/applications/{app_id}/drafts", json={"content": "Min tekst 2"})
    assert in_place.json()["id"] == saved.json()["id"]
    assert client.post(f"/api/applications/{app_id}/drafts",
                       json={"content": "x", "base_draft_id": 999}).status_code == 404

    # a question: answer only
    r = client.post(f"/api/applications/{app_id}/revise", json={"instruction": "Er åpningen for lang?"})
    task = wait_for(client, r.json()["task_id"])
    assert task["status"] == "done" and task["result"] == {"application_id": app_id, "draft_id": None}
    assert len(client.get(f"/api/applications/{app_id}/drafts").json()) == 2

    # an edit: a new agent version of the newest version
    r = client.post(f"/api/applications/{app_id}/revise", json={"instruction": "Gjør den kortere"})
    task = wait_for(client, r.json()["task_id"])
    assert task["status"] == "done", task
    v3 = task["result"]["draft_id"]
    new = client.get(f"/api/drafts/{v3}").json()
    assert (new["version"], new["author"], new["instruction"]) == (3, "agent", "Gjør den kortere")
    assert new["content"].startswith("Min tekst 2") and new["change_summary"].startswith("Endret etter")

    messages = client.get(f"/api/applications/{app_id}/messages").json()
    assert [(m["role"], m["draft_id"]) for m in messages] == [
        ("agent", v1), ("user", None), ("agent", None), ("user", None), ("agent", v3)
    ]
    assert messages[2]["text"] == "Mock-svar på spørsmålet."

    # the reviser got the previous chat as a log, not the current message
    reviser_req = writer_mod.get_backend().requests[-1]
    content = reviser_req.full_user_content()
    assert "<user_message>\nGjør den kortere\n</user_message>" in content
    assert "- Søker: Er åpningen for lang?" in content and "- Søker: Gjør den kortere" not in content

    # docx
    r = client.get(f"/api/drafts/{v3}/docx")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert "filename*=UTF-8''S%C3%B8knad%20Eksempel%20AS%20v3.docx" in r.headers["content-disposition"]
    text = "\n".join(p.text for p in Document(io.BytesIO(r.content)).paragraphs)
    assert "Testa Testesen" in text and "Eksempel AS" in text and "Min tekst 2" in text


def test_api_errors(client, session):
    job = add_job(session)
    assert client.post("/api/jobs/999/draft").status_code == 404
    assert client.get("/api/applications/999/drafts").status_code == 404
    assert client.get("/api/applications/999/messages").status_code == 404
    assert client.get("/api/drafts/999").status_code == 404
    assert client.get("/api/drafts/999/docx").status_code == 404
    app = Application(job_id=job.id, status="interessant")
    session.add(app)
    session.commit()
    r = client.post(f"/api/applications/{app.id}/revise", json={"instruction": "Kortere"})
    assert r.status_code == 409 and r.json()["code"] == "no_draft"
    assert client.get(f"/api/applications/{app.id}/messages").json() == []


def test_failed_writer_fails_task_and_leaves_job_untouched(client, session, monkeypatch):
    job = add_job(session)
    backend = MockBackend(lambda req: "ikke json" if req.output_schema.__name__ == "DraftResult"
                          else responder()(req))
    monkeypatch.setattr(writer_mod, "get_backend", lambda name=None: backend)
    task = wait_for(client, client.post(f"/api/jobs/{job.id}/draft").json()["task_id"])
    assert task["status"] == "failed" and task["message"].startswith("Skriveagenten feilet")
    assert client.get(f"/api/jobs/{job.id}").json()["application"] is None


# --- Export --------------------------------------------------------------------------------


def test_docx_helpers():
    assert filename('A/S "Test"', 2) == "Søknad A S Test v2.docx"
    assert sender_from_profile("name: Ola\ncontact:\n  email: ola@example.com\n  phone: '123'\n") == [
        "Ola", "ola@example.com", "123"
    ]
    assert sender_from_profile("navn: Kari\nepost: kari@example.com\n") == ["Kari", "kari@example.com"]
    assert sender_from_profile(None) == [] and sender_from_profile("- liste") == []


def test_docx_markdown():
    from jobsearcher.export.docx import letter_docx

    data = letter_docx("# Tittel\n\nEn **fet** og *kursiv* linje\nNy linje\n\n- punkt 1\n- punkt 2\n",
                       sender=["Ola"], recipient="Firma", on=datetime(2026, 10, 11).date())
    doc = Document(io.BytesIO(data))
    paras = [(p.text, p.style.name) for p in doc.paragraphs]
    assert paras[:3] == [("Ola", "Normal"), ("Firma", "Normal"), ("11. oktober 2026", "Normal")]
    assert ("En fet og kursiv linje\nNy linje", "Normal") in paras
    assert [t for t, s in paras if s == "List Bullet"] == ["punkt 1", "punkt 2"]
    bold = [r.text for p in doc.paragraphs for r in p.runs if r.bold]
    assert "fet" in bold and "Tittel" in bold


def test_clean_letter_removes_dashes():
    text = "Jeg bygde Matflote – en app for rester.\n– punkt\nStudert 2022–2025 — med A."
    out = clean_letter(text)
    assert "–" not in out and "—" not in out
    assert out == "Jeg bygde Matflote, en app for rester.\n- punkt\nStudert 2022-2025, med A."
