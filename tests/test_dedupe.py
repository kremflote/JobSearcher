from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import select

from jobsearcher.config import load_settings
from jobsearcher.db.models import Job, JobSource
from jobsearcher.pipeline.run import upsert_raw
from jobsearcher.sources.base import RawJob

NOW = datetime(2026, 10, 10, 6, 0, tzinfo=UTC)


@pytest.fixture
def settings():
    return load_settings()


def raw(**kw) -> RawJob:
    base = dict(source="nav", source_id="n1", title="Backend-utvikler", company="Fjordbølge Teknologi AS",
                municipality="OSLO", location_text="Oslo", description_html="<p>Vi søker en utvikler.</p>",
                published_at=NOW - timedelta(days=1))
    base.update(kw)
    return RawJob(**base)


def test_same_source_id_updates(session, settings):
    a = upsert_raw(session, raw(), settings, NOW)
    b = upsert_raw(session, raw(description_html="<p>Ny tekst.</p>"), settings, NOW + timedelta(hours=1))
    assert not b.is_new and b.job.id == a.job.id and b.content_changed
    assert b.job.description_clean == "Ny tekst."
    c = upsert_raw(session, raw(description_html="<p>Ny tekst.</p>"), settings, NOW + timedelta(hours=2))
    assert not c.content_changed


def test_application_url_merge_and_priority(session, settings):
    a = upsert_raw(session, raw(application_url="https://www.fjord.no/jobs/42?src=nav"), settings, NOW)
    b = upsert_raw(session, raw(source="finn_api", source_id="f1", title="Utvikler backend (Finn-tittel)",
                                application_url="https://fjord.no/jobs/42/", description_html=None,
                                deadline=datetime(2026, 11, 1).date()), settings, NOW)
    assert b.job.id == a.job.id
    # NAV is primary: its title wins, Finn only fills gaps.
    assert b.job.title == "Backend-utvikler"
    assert b.job.deadline == datetime(2026, 11, 1).date()
    sources = session.exec(select(JobSource.source).where(JobSource.job_id == a.job.id)).all()
    assert sorted(sources) == ["finn_api", "nav"]


def test_fuzzy_title_merge(session, settings):
    a = upsert_raw(session, raw(), settings, NOW)
    b = upsert_raw(session, raw(source="finn_api", source_id="f1", title="Backend utvikler", company="Fjordbølge Teknologi"),
                   settings, NOW)
    assert b.job.id == a.job.id
    # Different location → not merged.
    c = upsert_raw(session, raw(source="finn_api", source_id="f2", municipality="Bergen", location_text="Bergen"),
                   settings, NOW)
    assert c.is_new


def test_org_number_beats_name(session, settings):
    a = upsert_raw(session, raw(org_number="999888777"), settings, NOW)
    b = upsert_raw(session, raw(source="finn_api", source_id="f1", org_number="111222333"), settings, NOW)
    assert b.is_new and b.job.id != a.job.id


def test_uncertain_match_logged_not_merged(session, settings, caplog):
    upsert_raw(session, raw(title="Backend-utvikler Java"), settings, NOW)
    with caplog.at_level("WARNING"):
        b = upsert_raw(session, raw(source="finn_api", source_id="f1", title="Backend-utvikler Kotlin"),
                       settings, NOW)
    assert b.is_new
    assert any("uncertain duplicate" in r.message for r in caplog.records)


def test_repost_of_inactive_job(session, settings):
    a = upsert_raw(session, raw(), settings, NOW)
    a.job.active = False
    session.add(a.job)
    session.flush()
    b = upsert_raw(session, raw(source_id="n2"), settings, NOW + timedelta(days=40))
    assert b.is_new and b.job.reposted_from_id == a.job.id


def test_repost_of_old_active_job(session, settings):
    a = upsert_raw(session, raw(published_at=NOW - timedelta(days=45)), settings, NOW - timedelta(days=45))
    b = upsert_raw(session, raw(source="finn_api", source_id="f9", published_at=NOW), settings, NOW)
    assert b.is_new and b.job.reposted_from_id == a.job.id
    assert session.get(Job, a.job.id).active is False


def test_contacts_deduplicated(session, settings):
    contacts = [{"name": "Kari Nordmann", "email": "kari@example.invalid"}]
    a = upsert_raw(session, raw(contacts=contacts), settings, NOW)
    upsert_raw(session, raw(contacts=contacts + [{"name": "Ola Testesen"}]), settings, NOW)
    from jobsearcher.db.models import JobContact

    names = session.exec(select(JobContact.name).where(JobContact.job_id == a.job.id)).all()
    assert sorted(names) == ["Kari Nordmann", "Ola Testesen"]


def test_finn_position_title_used_for_cross_source_match():
    from jobsearcher.db.models import Job
    from jobsearcher.pipeline.dedupe import best_title_score
    from jobsearcher.sources.base import RawJob

    job = Job(fingerprint="f", title="Junior utvikler", company="Fjordbyte AS", company_slug="fjordbyte")
    raw = RawJob(
        source="finn_api", source_id="9000001", title="Vil du være med og forme fremtidens apper?",
        meta={"job_title": "Junior utvikler"},
    )
    assert best_title_score(job, raw) >= 90
