"""Rule-based hard filter (ARCHITECTURE §5.1, §5.3).

Rules return `(rule, detail)` pairs; an empty list means the job passes. Rules that only
need title/location run before detail fetching (`pre_detail_rules`), so we do not fetch ad
text for jobs that are obviously out. Rules on the ad text run after (`post_detail_rules`).
Finn API jobs are prefiltered on experience/education server side and get only geography
and role rules.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlmodel import Session

from jobsearcher.config import Locations, Settings
from jobsearcher.db.models import HardfilterLog, Job

Hit = tuple[str, str]

NORWAY = {"norge", "norway", "no", "nor"}

# Oslo districts, to tell when an ad names a district outside a mode's `oslo_bydeler`.
OSLO_BYDELER = {
    "alna", "bjerke", "frogner", "gamle oslo", "grorud", "grünerløkka", "nordre aker",
    "nordstrand", "sagene", "st. hanshaugen", "stovner", "søndre nordstrand", "ullern",
    "vestre aker", "østensjø",
}

# Occupation keywords that mark an ad as IT (any hit keeps the job).
IT_OCCUPATION = re.compile(
    r"\bit\b|ikt|data|utvikl|program|software|system|teknolog|developer|devops|nettverk|"
    r"applikasjon|frontend|backend|fullstack|web|digital|ingeniør|engineer|tech",
    re.IGNORECASE,
)
# Occupation keywords that are clearly not IT. Only used when no IT keyword matches.
NON_IT_OCCUPATION = re.compile(
    r"helse|sykepleie|lege|omsorg|sosial|pleie|barnehage|undervisning|lærer|butikk|salg|"
    r"varehandel|restaurant|kokk|servering|reiseliv|bygg og anlegg|håndverk|tømrer|elektriker|"
    r"rørlegger|renhold|transport|sjåfør|lager|logistikk|jordbruk|fiske|industri|produksjon|"
    r"frisør|kunst|kultur|politi|forsvar|vakt|eiendom|regnskap|økonomi|kontor og administrasjon|"
    r"juss|jus\b|advokat|bank|finans|forsikring|markedsføring|media|kommunikasjon|kirke",
    re.IGNORECASE,
)

_NUM_WORDS = {
    "en": 1, "ett": 1, "one": 1, "to": 2, "two": 2, "tre": 3, "three": 3, "fire": 4, "four": 4,
    "fem": 5, "five": 5, "seks": 6, "six": 6, "syv": 7, "sju": 7, "seven": 7, "åtte": 8,
    "eight": 8, "ni": 9, "nine": 9, "ti": 10, "ten": 10,
}
_NUM = r"(\d{1,2}|" + "|".join(_NUM_WORDS) + r")"
# "3 års erfaring", "3+ years of experience", "2-4 år relevant erfaring", "minimum tre års erfaring"
_YEARS_EXP = re.compile(
    r"(?<![\d\w-])" + _NUM + r"\s*(?:\+|[-–]\s*\d{1,2})?\s*(?:års?|years?|yrs)\b"
    r"(?P<tail>[^.\n]{0,50})",
    re.IGNORECASE,
)
_EXPERIENCE_WORD = re.compile(r"erfaring|experience", re.IGNORECASE)
# Company self-descriptions ("vi har over 20 års erfaring") are not requirements.
_SELF_DESCRIPTION = re.compile(
    r"(vi har|we have|selskapet har|har over|med over|har mer enn|in business for|siden)\s*\S*\s*$",
    re.IGNORECASE,
)


def word_pattern(word: str) -> re.Pattern[str]:
    """Short words (≤ 3 chars, e.g. "SOC") match whole words only; longer words match
    anywhere, so Norwegian compounds ("informasjonssikkerhet", "teamleder") are caught."""
    w = re.escape(word.strip())
    if len(word.strip()) <= 3:
        return re.compile(rf"(?<!\w){w}(?!\w)", re.IGNORECASE)
    return re.compile(w, re.IGNORECASE)


def _first_hit(words: list[str], text: str) -> str | None:
    for word in words:
        if word.strip() and word_pattern(word).search(text):
            return word
    return None


# --- Rules ---------------------------------------------------------------------------


def job_type_rule(job: Job, settings: Settings) -> Hit | None:
    if settings.search.job_types.get(job.job_type, True) is False:
        return ("job_type", f"jobbtypen {job.job_type} er slått av")
    return None


def geography_rule(job: Job, settings: Settings, locations: Locations) -> Hit | None:
    country = (job.meta or {}).get("country")
    if country and str(country).strip().lower() not in NORWAY:
        return ("geography", f"utlandet: {country}")
    mode_name = settings.search.geography.get(job.job_type) or settings.search.geography.get("unknown", "oslo_omegn")
    mode = locations.modes.get(mode_name)
    if mode is None or mode.all:
        return None
    if job.remote == "full" and settings.search.allow_remote_norway:
        return None
    if not job.municipality and not job.location_text:
        return None  # unknown location: keep, the LLM/user decides
    allowed = {m.lower() for m in mode.municipalities}
    muni = (job.municipality or "").lower()
    loc = (job.location_text or "").lower()
    if muni in allowed:
        if muni == "oslo" and mode.oslo_bydeler:
            wanted = {b.lower() for b in mode.oslo_bydeler}
            named = {b for b in OSLO_BYDELER if re.search(rf"\b{re.escape(b)}\b", loc)}
            if named and not named & wanted:
                return ("geography", f"Oslo bydel {', '.join(sorted(named))} er utenfor modus {mode_name}")
        return None
    # Multi-location ads: any allowed municipality named in the location text passes.
    if any(re.search(rf"\b{re.escape(m)}\b", loc) for m in allowed):
        return None
    return ("geography", f"{job.municipality or job.location_text} er utenfor modus {mode_name} ({job.job_type})")


# Words that contain an exclude word but are not security roles ("IT & Cybernetics").
ROLE_EXCLUDE_EXCEPTIONS = re.compile(r"cybernetic\w*|kybernetikk\w*", re.IGNORECASE)


def role_rule(job: Job, settings: Settings) -> Hit | None:
    occupation = " ".join((job.meta or {}).get("occupation") or [])
    text = ROLE_EXCLUDE_EXCEPTIONS.sub(" ", f"{job.title} \n {occupation}")
    word = _first_hit(settings.search.role_exclude, text)
    if word:
        return ("role", f"ekskluderingsord «{word}»")
    return None


def occupation_rule(job: Job) -> Hit | None:
    """Clearly non-IT occupation categories (NAV). Unknown or mixed → keep."""
    occupation = [o for o in (job.meta or {}).get("occupation") or [] if o]
    if not occupation:
        return None
    joined = " | ".join(occupation)
    if IT_OCCUPATION.search(joined):
        return None
    if NON_IT_OCCUPATION.search(joined):
        return ("occupation", f"yrkeskategori ikke IT: {joined}")
    return None


def title_relevance_rule(job: Job, settings: Settings) -> Hit | None:
    """Unfiltered sources without occupation data (NAV before details): the title must
    look like an IT or entry-level job, so we don't fetch details for every ad in Oslo."""
    if job.prefiltered or (job.meta or {}).get("occupation"):
        return None
    words = settings.search.title_require_any
    if not words or _first_hit(words, job.title):
        return None
    return ("title_not_it", "tittelen ligner ikke en IT- eller nyutdannet-stilling")


def seniority_title_rule(job: Job, settings: Settings) -> Hit | None:
    if job.prefiltered:
        return None
    word = _first_hit(settings.search.seniority_title_exclude, job.title)
    if word:
        return ("seniority_title", f"tittel inneholder «{word}»")
    return None


def required_years(text: str) -> int | None:
    """Highest lower bound of required years of experience found in `text`, or None."""
    found: list[int] = []
    for m in _YEARS_EXP.finditer(text):
        raw = m.group(1).lower()
        years = int(raw) if raw.isdigit() else _NUM_WORDS[raw]
        if years > 15:
            continue  # "20 års erfaring" is almost always the company describing itself
        before = text[max(0, m.start() - 40) : m.start()]
        near = m.group("tail") + " " + before[-30:]
        if not _EXPERIENCE_WORD.search(near):
            continue
        if _SELF_DESCRIPTION.search(before):
            continue
        found.append(years)
    return max(found) if found else None


def experience_rule(job: Job, settings: Settings) -> Hit | None:
    if job.prefiltered or not job.description_clean:
        return None
    years = required_years(job.description_clean)
    if years is not None and years > settings.search.max_required_experience_years:
        return ("experience_years", f"krever {years} års erfaring")
    return None


# --- Entry points ----------------------------------------------------------------------


def pre_detail_rules(job: Job, settings: Settings, locations: Locations) -> list[Hit]:
    """Rules on title, location and categories (before the ad text is fetched)."""
    hits = [
        job_type_rule(job, settings),
        geography_rule(job, settings, locations),
        role_rule(job, settings),
        occupation_rule(job),
        seniority_title_rule(job, settings),
    ]
    found = [h for h in hits if h]
    # Weakest reason; only logged when nothing else already discards the job.
    if not found and (hit := title_relevance_rule(job, settings)):
        found.append(hit)
    return found


def post_detail_rules(job: Job, settings: Settings) -> list[Hit]:
    """Rules on the ad text (after details are fetched and cleaned)."""
    hits = [experience_rule(job, settings)]
    return [h for h in hits if h]


def discard(session: Session, job: Job, hits: list[Hit]) -> None:
    """Mark the job filtered out and log why (hardfilter_log)."""
    if not hits:
        return
    job.filtered_out = True
    session.add(job)
    session.flush()
    now = datetime.now(UTC)
    for rule, detail in hits:
        session.add(HardfilterLog(job_id=job.id, rule=rule, detail=detail, created_at=now))
