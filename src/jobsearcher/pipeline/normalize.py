"""Field normalization (ARCHITECTURE §4.5, §5.4).

Pure functions: fingerprint, company slug, normalized application URL, municipality
canonicalization, job type, remote detection, ad language and content hash.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date
from urllib.parse import urlsplit, urlunsplit

# Legal-form suffixes stripped from company names before fingerprint/slug.
COMPANY_SUFFIXES = {
    "as", "asa", "sa", "ans", "da", "ba", "nuf", "ks", "ab", "ltd", "inc", "gmbh", "llc", "plc",
    "oy", "aps", "bv", "corp",
}
UNKNOWN_COMPANY = "Ukjent arbeidsgiver"
UNKNOWN_SLUG = "ukjent"

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")


def _clean_words(text: str) -> list[str]:
    text = _PUNCT.sub(" ", text.lower().replace("_", " "))
    return _WS.sub(" ", text).strip().split()


def normalize_company(name: str | None) -> str:
    """Lower case, no punctuation, no legal-form suffixes ("Acme Norge AS" → "acme norge")."""
    if not name:
        return ""
    # "A/S" → "as" before punctuation removal splits it.
    name = re.sub(r"\bA/S\b", "AS", name, flags=re.IGNORECASE)
    words = [w for w in _clean_words(name) if w not in COMPANY_SUFFIXES]
    return " ".join(words)


def normalize_text(text: str | None) -> str:
    return " ".join(_clean_words(text or ""))


_TRANSLIT = str.maketrans({"æ": "ae", "ø": "o", "å": "a"})


def company_slug(name: str | None) -> str:
    """URL-safe slug of the normalized company name; `UNKNOWN_SLUG` if no name."""
    norm = normalize_company(name).translate(_TRANSLIT)
    norm = unicodedata.normalize("NFKD", norm).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", norm).strip("-")
    return slug or UNKNOWN_SLUG


def fingerprint(company: str | None, title: str, municipality: str | None) -> str:
    """`company | title | municipality`, lower case, without punctuation and legal suffixes."""
    return f"{normalize_company(company)} | {normalize_text(title)} | {normalize_text(municipality)}"


# --- URLs ------------------------------------------------------------------------


def normalize_url(url: str | None) -> str | None:
    """Scheme-less lower-case host without `www.`, path without trailing slash, no query/fragment."""
    if not url or not url.strip():
        return None
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    parts = urlsplit(url)
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return None
    path = parts.path.rstrip("/")
    return urlunsplit(("", host, path, "", "")).lstrip("/")


# Paths that are generic listing pages, not one specific ad: never used for URL matching.
_GENERIC_PATHS = {
    "", "jobs", "jobb", "karriere", "career", "careers", "ledige-stillinger", "stillinger",
    "jobbe-hos-oss", "jobs/list", "connect", "apply", "sok", "search",
}


def is_specific_url(url_norm: str | None) -> bool:
    """True when the normalized URL points at something more specific than a careers index."""
    if not url_norm or "/" not in url_norm:
        return False
    path = url_norm.split("/", 1)[1].strip("/").lower()
    return path not in _GENERIC_PATHS


# --- Municipality -------------------------------------------------------------------

# Postal places and districts → municipality (Oslo area, where the geography filter matters).
PLACE_ALIASES = {
    "fornebu": "Bærum", "lysaker": "Bærum", "sandvika": "Bærum", "stabekk": "Bærum",
    "høvik": "Bærum", "bekkestua": "Bærum", "bærums verk": "Bærum", "rud": "Bærum",
    "kjeller": "Lillestrøm", "strømmen": "Lillestrøm", "skedsmokorset": "Lillestrøm",
    "skjetten": "Lillestrøm", "fetsund": "Lillestrøm", "sørumsand": "Lillestrøm",
    "lillestrøm": "Lillestrøm", "skedsmo": "Lillestrøm",
    "hagan": "Nittedal", "rotnes": "Nittedal",
    "gardermoen": "Ullensaker", "jessheim": "Ullensaker", "kløfta": "Ullensaker",
    "fjellhamar": "Lørenskog", "rasta": "Lørenskog",
    "fjerdingby": "Rælingen",
    "ask": "Gjerdrum",
}

# Counties and other non-municipality locations: never returned as municipality.
NON_MUNICIPALITIES = {
    "norge", "norway", "hele landet", "akershus", "viken", "østfold", "buskerud", "vestfold",
    "telemark", "agder", "rogaland", "vestland", "møre og romsdal", "trøndelag", "nordland",
    "troms", "finnmark", "innlandet", "troms og finnmark", "vestfold og telemark", "utlandet",
    "remote", "fjernarbeid", "hjemmekontor",
}

_LOWER_WORDS = {"og", "i", "på"}
_POSTCODE = re.compile(r"\b\d{4}\b")


def _title_case(name: str) -> str:
    def word(w: str, first: bool) -> str:
        if not first and w.lower() in _LOWER_WORDS:
            return w.lower()
        return "-".join(p[:1].upper() + p[1:].lower() for p in w.split("-"))

    return " ".join(word(w, i == 0) for i, w in enumerate(name.split()))


def canonical_municipality(name: str | None) -> str | None:
    """"OSLO" → "Oslo", "0150 Oslo" → "Oslo", "Fornebu" → "Bærum", county names → None."""
    if not name:
        return None
    name = _WS.sub(" ", _POSTCODE.sub(" ", name)).strip(" ,.-")
    if not name:
        return None
    low = name.lower()
    if low in PLACE_ALIASES:
        return PLACE_ALIASES[low]
    if low in NON_MUNICIPALITIES:
        return None
    return _title_case(name)


def municipality_from_location(location_text: str | None) -> str | None:
    """Best-effort municipality from a free location string like "Storgata 1, 0155 Oslo".

    Prefers the part with a postal code; otherwise the first part that is a place, not a
    county. Multi-location strings ("Oslo, Bergen") return the first.
    """
    if not location_text:
        return None
    parts = [p.strip() for p in re.split(r"[,;/\n]| og ", location_text) if p.strip()]
    for part in parts:
        if _POSTCODE.search(part):
            m = canonical_municipality(part)
            if m:
                return m
    for part in parts:
        if any(ch.isdigit() for ch in part):
            continue  # street address
        m = canonical_municipality(part)
        if m:
            return m
    return None


def municipality(raw_municipality: str | None, location_text: str | None) -> str | None:
    return canonical_municipality(raw_municipality) or municipality_from_location(location_text)


# --- Job type ---------------------------------------------------------------------

_SUMMER = re.compile(
    r"sommerjobb|sommerstudent|sommerintern|sommerprosjekt|sommervikar|summer\s*(intern|job|student)"
    r"|\binternship|\bintern\b|feriejobb",
    re.IGNORECASE,
)
_TRAINEE = re.compile(r"trainee", re.IGNORECASE)
_GRADUATE = re.compile(r"graduate|nyutdannet\s*program|graduateprogram", re.IGNORECASE)

_EMPLOYMENT_TYPES = {
    "fast": "permanent",
    "fast ansettelse": "permanent",
    "permanent": "permanent",
    "trainee": "trainee",
    "feriejobb": "summer",
    "sommerjobb": "summer",
    "sesong": "summer",
}


def job_type(hint: str | None, title: str, employment_type: str | None = None) -> str:
    """trainee | graduate | summer | permanent | unknown (§5.4).

    A specific hint (trainee/graduate/summer) wins; then the title; a `permanent` hint (from a
    generic full-time search) only applies when the title says nothing; then employment type.
    """
    if hint in ("trainee", "graduate", "summer"):
        return hint
    if _SUMMER.search(title):
        return "summer"
    if _TRAINEE.search(title):
        return "trainee"
    if _GRADUATE.search(title):
        return "graduate"
    if hint == "permanent":
        return "permanent"
    if employment_type:
        mapped = _EMPLOYMENT_TYPES.get(employment_type.strip().lower())
        if mapped:
            return mapped
        if _SUMMER.search(employment_type):
            return "summer"
    return "unknown"


# --- Remote -----------------------------------------------------------------------

_REMOTE_FULL = re.compile(
    r"100\s*%\s*(remote|hjemmekontor)|fully\s+remote|full\s+remote|helt\s+remote|remote[- ]first"
    r"|remote\s+only|kun\s+remote|fjernarbeid",
    re.IGNORECASE,
)
_REMOTE_HYBRID = re.compile(r"\bhybrid\b|hjemmekontor|delvis\s+remote|\bremote\b", re.IGNORECASE)


def detect_remote(explicit: str | None, title: str, location_text: str | None, text: str | None) -> str | None:
    """`full`/`hybrid` from cheap keyword checks; None when nothing says so (unknown)."""
    if explicit:
        return explicit
    loc = (location_text or "").strip().lower()
    if loc in {"remote", "fjernarbeid", "hjemmekontor"}:
        return "full"
    haystack = " ".join(filter(None, [title, location_text, (text or "")[:6000]]))
    if _REMOTE_FULL.search(haystack):
        return "full"
    if _REMOTE_HYBRID.search(haystack):
        return "hybrid"
    return None


# --- Language ---------------------------------------------------------------------

_NO_WORDS = {
    "og", "er", "på", "til", "med", "som", "det", "vi", "du", "av", "har", "skal", "deg",
    "ikke", "eller", "hos", "vår", "våre", "oss", "stillingen", "søknad",
}
_EN_WORDS = {
    "and", "the", "is", "to", "of", "with", "we", "you", "are", "our", "will", "in", "your",
    "this", "be", "have", "position", "team",
}


def ad_language(title: str, text: str | None) -> str | None:
    """"no" or "en" by counting common function words; None when there is no signal."""
    words = _clean_words(f"{title} {(text or '')[:5000]}")
    no = sum(1 for w in words if w in _NO_WORDS)
    en = sum(1 for w in words if w in _EN_WORDS)
    if no == en == 0:
        return None
    return "en" if en > no else "no"


# --- Hashes -------------------------------------------------------------------------


def text_hash(text: str | None) -> str | None:
    if not text:
        return None
    return hashlib.sha256(_WS.sub(" ", text).strip().encode("utf-8")).hexdigest()[:16]


def content_hash(
    *,
    title: str,
    company: str | None,
    location_text: str | None,
    deadline: date | None,
    deadline_text: str | None,
    application_url: str | None,
    text_digest: str | None,
) -> str:
    """Hash over key fields and the full cleaned ad text (via `text_hash`).

    A change means the ad changed and the job is re-scored (§5.5).
    """
    parts = [
        normalize_text(title),
        normalize_company(company),
        normalize_text(location_text),
        deadline.isoformat() if deadline else "",
        (deadline_text or "").strip().lower(),
        normalize_url(application_url) or "",
        text_digest or "",
    ]
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]
