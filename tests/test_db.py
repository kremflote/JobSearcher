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
