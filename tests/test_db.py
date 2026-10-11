from sqlmodel import select

from jobsearcher.db.models import Job, Task


def test_migrated_db_roundtrip(session):
    session.add(Job(fingerprint="f", title="Utvikler", company="Eksempel AS", company_slug="eksempel"))
    session.add(Task(id="t1", kind="run"))
    session.commit()
    job = session.exec(select(Job)).one()
    assert job.meta == {} and job.active and job.first_seen
    assert session.get(Task, "t1").params == {}


def test_settings_load():
    from jobsearcher.config import load_locations, load_settings, load_sources

    s = load_settings({"search.geography.permanent": "nittedal"})
    assert s.search.geography["permanent"] == "nittedal"
    assert s.search.unspecified_seniority_max_score == 65
    assert "oslo_omegn" in load_locations().modes
    assert "it_norge" in load_sources()["finn_api"]["searches"]


def test_datetimes_roundtrip_aware(session):
    session.add(Task(id="t2", kind="run"))
    session.commit()
    session.expunge_all()
    assert session.get(Task, "t2").created_at.tzinfo is not None


def test_migration_0003_adds_fallback_from(engine):
    from sqlalchemy import inspect

    from jobsearcher.db.models import AgentRun

    cols = {c["name"]: c for c in inspect(engine).get_columns("agent_runs")}
    assert cols["fallback_from"]["nullable"] is True
    from sqlmodel import Session

    with Session(engine) as s:
        s.add(AgentRun(agent="filter", backend="openrouter", fallback_from="claude_code", model="m",
                       prompt_version="1"))
        s.commit()
        assert s.exec(select(AgentRun)).one().fallback_from == "claude_code"


def test_migration_0003_downgrade(engine):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    from jobsearcher.config import ROOT

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "src" / "jobsearcher" / "db" / "migrations"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.downgrade(cfg, "7c3e9a1f4b20")
    assert "fallback_from" not in {c["name"] for c in inspect(engine).get_columns("agent_runs")}
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
    assert "fallback_from" in {c["name"] for c in inspect(engine).get_columns("agent_runs")}
