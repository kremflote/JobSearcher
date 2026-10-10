import pytest

from jobsearcher.config import load_locations, load_settings
from jobsearcher.db.models import Job
from jobsearcher.pipeline import hardfilter as H


@pytest.fixture
def settings():
    return load_settings()


@pytest.fixture
def locations():
    return load_locations()


def job(**kw) -> Job:
    base = dict(fingerprint="x", title="Utvikler", company="Firma", company_slug="firma",
                municipality="Oslo", location_text="Oslo", job_type="permanent", meta={})
    base.update(kw)
    return Job(**base)


def rules(j, settings, locations):
    return [r for r, _ in H.pre_detail_rules(j, settings, locations) + H.post_detail_rules(j, settings)]


def test_geography(settings, locations):
    assert rules(job(), settings, locations) == []
    assert rules(job(municipality="Bergen", location_text="Bergen"), settings, locations) == ["geography"]
    # Trainee: whole Norway.
    assert rules(job(municipality="Bergen", location_text="Bergen", job_type="trainee"), settings, locations) == []
    # Remote in Norway passes.
    assert rules(job(municipality="Bergen", location_text="Bergen", remote="full"), settings, locations) == []
    # Abroad is always out.
    assert rules(job(job_type="trainee", meta={"country": "Sverige"}), settings, locations) == ["geography"]
    # Multi-location text naming an allowed municipality passes.
    assert rules(job(municipality="Bergen", location_text="Bergen, Oslo"), settings, locations) == []
    # Unknown location is kept.
    assert rules(job(municipality=None, location_text=None), settings, locations) == []


def test_role_exclude_word_boundaries(settings, locations):
    assert rules(job(title="SOC-analytiker"), settings, locations) == ["role"]
    assert rules(job(title="Utvikler med social media-fokus"), settings, locations) == []
    assert rules(job(title="Rådgiver informasjonssikkerhet"), settings, locations) == ["role"]
    assert rules(job(title="Cybersecurity Engineer"), settings, locations) == ["role"]
    assert rules(job(title="Summer Internship - IT & Cybernetics"), settings, locations) == []


def test_seniority_only_for_unfiltered(settings, locations):
    assert rules(job(title="Senior utvikler"), settings, locations) == ["seniority_title"]
    assert rules(job(title="Teamleder utvikling"), settings, locations) == ["seniority_title"]
    assert rules(job(title="Senior utvikler", prefiltered=True), settings, locations) == []


def test_occupation(settings, locations):
    assert rules(job(meta={"occupation": ["Helse og sosial", "Sykepleier"]}), settings, locations) == ["occupation"]
    assert rules(job(meta={"occupation": ["IT", "Utvikling"]}), settings, locations) == []
    assert rules(job(meta={"occupation": ["Uklassifisert"]}), settings, locations) == []
    assert rules(job(meta={"occupation": ["Salg", "IT-salg"]}), settings, locations) == []


@pytest.mark.parametrize(
    ("text", "years"),
    [
        ("Du har minst 3 års erfaring med Java.", 3),
        ("Krav: 2-4 år relevant erfaring.", 2),
        ("3+ years of experience with Python", 3),
        ("Minimum tre års erfaring fra utvikling", 3),
        ("0-2 års erfaring er fint.", 0),
        ("Vi har over 20 års erfaring med konsulentvirksomhet.", None),
        ("Selskapet har 5 års erfaring i bransjen.", None),
        ("Vi har vært i drift i 10 år.", None),
        ("Ingen krav til erfaring.", None),
    ],
)
def test_required_years(text, years):
    assert H.required_years(text) == years


def test_experience_rule(settings, locations):
    assert rules(job(description_clean="Du har 2 års erfaring."), settings, locations) == ["experience_years"]
    assert rules(job(description_clean="Du har 2 års erfaring.", prefiltered=True), settings, locations) == []
    assert rules(job(description_clean="Nyutdannet? Ingen erfaring kreves."), settings, locations) == []


def test_job_type_disabled(locations):
    s = load_settings({"search.job_types.summer": False})
    assert "job_type" in rules(job(job_type="summer"), s, locations)


def test_title_relevance_rule_only_without_occupation():
    from jobsearcher.config import load_settings
    from jobsearcher.db.models import Job
    from jobsearcher.pipeline.hardfilter import title_relevance_rule

    s = load_settings()
    nav = lambda title, **kw: Job(fingerprint="f", title=title, company="X", company_slug="x", **kw)  # noqa: E731
    assert title_relevance_rule(nav("Butikkmedarbeider"), s)[0] == "title_not_it"
    assert title_relevance_rule(nav("Junior utvikler"), s) is None
    assert title_relevance_rule(nav("Trainee 2027"), s) is None
    assert title_relevance_rule(nav("IT-konsulent"), s) is None
    assert title_relevance_rule(nav("Butikkmedarbeider", prefiltered=True), s) is None
    assert title_relevance_rule(nav("Butikkmedarbeider", meta={"occupation": ["Salg"]}), s) is None
