from datetime import date

from jobsearcher.pipeline import normalize as N


def test_fingerprint_strips_suffix_and_punctuation():
    assert N.fingerprint("Eksempel Data AS", "Utvikler (Java/Kotlin)!", "OSLO") == "eksempel data | utvikler java kotlin | oslo"
    assert N.fingerprint("Eksempel Data ASA", "utvikler java kotlin", "Oslo") == N.fingerprint(
        "eksempel data", "Utvikler – Java, Kotlin", "oslo"
    )


def test_company_slug():
    assert N.company_slug("Fjordbølge Teknologi AS") == "fjordbolge-teknologi"
    assert N.company_slug("Blåbær A/S") == "blabaer"
    assert N.company_slug(None) == N.UNKNOWN_SLUG


def test_normalize_url():
    assert N.normalize_url("https://www.Example.no/jobs/123/?utm_source=finn#apply") == "example.no/jobs/123"
    assert N.normalize_url("http://example.no/jobs/123") == "example.no/jobs/123"
    assert N.normalize_url("") is None
    assert N.is_specific_url("example.no/jobs/123")
    assert not N.is_specific_url("example.no/karriere")
    assert not N.is_specific_url("example.no")


def test_municipality():
    assert N.canonical_municipality("OSLO") == "Oslo"
    assert N.canonical_municipality("NORD-AURDAL") == "Nord-Aurdal"
    assert N.canonical_municipality("0150 Oslo") == "Oslo"
    assert N.canonical_municipality("Fornebu") == "Bærum"
    assert N.canonical_municipality("Akershus") is None
    assert N.municipality(None, "Storgata 1, 0155 Oslo") == "Oslo"
    assert N.municipality(None, "Kjeller, Akershus") == "Lillestrøm"
    assert N.municipality(None, "Norge") is None
    assert N.municipality("LØRENSKOG", "whatever") == "Lørenskog"


def test_job_type():
    assert N.job_type(None, "Sommerjobb som utvikler") == "summer"
    assert N.job_type(None, "Summer Intern – Software") == "summer"
    assert N.job_type(None, "Internship in backend") == "summer"
    assert N.job_type(None, "IT-trainee 2027") == "trainee"
    assert N.job_type(None, "Graduate Developer") == "graduate"
    assert N.job_type("permanent", "Sommerjobb 2027") == "summer"
    assert N.job_type("trainee", "Utvikler") == "trainee"
    assert N.job_type("permanent", "Utvikler") == "permanent"
    assert N.job_type(None, "Utvikler", "Fast") == "permanent"
    assert N.job_type(None, "Utvikler", "Feriejobb") == "summer"
    assert N.job_type(None, "Utvikler", "Vikariat") == "unknown"


def test_detect_remote():
    assert N.detect_remote("hybrid", "x", None, None) == "hybrid"
    assert N.detect_remote(None, "Utvikler", "Remote", None) == "full"
    assert N.detect_remote(None, "Utvikler", "Oslo", "Stillingen er 100% remote.") == "full"
    assert N.detect_remote(None, "Utvikler", "Oslo", "Mulighet for hjemmekontor.") == "hybrid"
    assert N.detect_remote(None, "Utvikler", "Oslo", "Kontor i sentrum.") is None


def test_ad_language():
    assert N.ad_language("Utvikler", "Vi søker deg som har lyst til å jobbe med oss og vårt team.") == "no"
    assert N.ad_language("Developer", "We are looking for you to join our team and the company.") == "en"
    assert N.ad_language("", None) is None


def test_content_hash_changes_with_text_and_deadline():
    base = dict(title="Utvikler", company="A AS", location_text="Oslo", deadline=date(2026, 11, 1),
                deadline_text=None, application_url="https://a.no/jobs/1", text_digest=N.text_hash("tekst"))
    h = N.content_hash(**base)
    assert h == N.content_hash(**{**base, "company": "A"})
    assert h != N.content_hash(**{**base, "text_digest": N.text_hash("annen tekst")})
    assert h != N.content_hash(**{**base, "deadline": date(2026, 11, 2)})
