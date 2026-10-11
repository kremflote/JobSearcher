"""Agent output schemas (ARCHITECTURE §7.2).

The JSON schema sent to the model (`llm.base.output_json_schema`) has no numeric or length
bounds; the validators below clamp and trim instead of failing, so a slightly-off answer does
not cost a retry.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field


def _max_items(n: int):
    return AfterValidator(lambda v: v[:n])


def _lenient_date(v: Any) -> Any:
    if v in (None, ""):
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _clamp_score(v: int) -> int:
    return max(0, min(100, v))


def _blank_to_none(v: Any) -> Any:
    return None if isinstance(v, str) and not v.strip() else v


OptStr = Annotated[str | None, BeforeValidator(_blank_to_none)]


class Contact(BaseModel):
    name: str
    role: OptStr = None
    email: OptStr = None
    phone: OptStr = None


class FilterResult(BaseModel):
    job_id: str = Field(description="id-attributtet fra <job_ad>")
    score: Annotated[int, AfterValidator(_clamp_score)] = Field(description="0–100")
    confidence: Literal["high", "low"]
    role_category: Literal["backend", "frontend", "fullstack", "mobile", "devops", "data", "other"]
    job_type: Literal["trainee", "graduate", "summer", "permanent", "unknown"]
    seniority: Literal["entry", "unspecified", "experienced"]
    tech: list[str]
    summary: str = Field(description="2–4 setninger: hva jobben er")
    key_requirements: Annotated[list[str], _max_items(6)] = Field(description="maks 6")
    match_reasons: Annotated[list[str], _max_items(4)] = Field(description="maks 4")
    concerns: Annotated[list[str], _max_items(4)] = Field(description="maks 4")
    deadline: Annotated[date | None, BeforeValidator(_lenient_date)] = Field(description="YYYY-MM-DD eller null")
    deadline_text: OptStr = Field(description='f.eks. "snarest", "fortløpende"')
    contacts: list[Contact]
    application_url: OptStr
    ad_language: Literal["no", "en"]


class FilterBatchResult(BaseModel):
    results: list[FilterResult]


class DistilledProfile(BaseModel):
    profile_short: str = Field(description="Markdown, maks ~500 tokens")
    profile_long: str = Field(description="Markdown, maks ~3000 tokens")
    voice: str = Field(description="Markdown, maks ~800 tokens")


class CompanyNote(BaseModel):
    what_they_do: str
    size_and_locations: OptStr
    tech_and_engineering: OptStr = Field(description="stack, techblogg, open source")
    recent_news: Annotated[list[str], _max_items(3)] = Field(description="maks 3, med måned og år")
    culture_and_values: OptStr
    hooks_for_letter: Annotated[list[str], _max_items(4)] = Field(
        description="2–4 konkrete ting brevet kan koble seg til"
    )
    sources: list[str] = Field(description="URL-er du faktisk brukte")


class DraftResult(BaseModel):
    language: Literal["no", "en"]
    letter_markdown: str = Field(description="Bare brevteksten, uten adresse- og datoblokk")
    used_projects: list[str] = Field(description="Titler på prosjektene brevet bruker")
    claims_to_verify: list[str] = Field(description="Påstander om søkeren som ikke er dekket av profilen")
    notes_for_user: OptStr = Field(description="F.eks. at annonsen ber om vitnemål")


class RevisionResult(BaseModel):
    kind: Literal["revision", "answer"] = Field(description="answer = bare svar, ingen ny versjon")
    reply: str = Field(description="Svaret i chatten; ved revision én setning om hva som ble endret")
    letter_markdown: str = Field(description="Hele det reviderte brevet ved revision, ellers tom")
    claims_to_verify: list[str]


SCHEMAS: dict[str, type[BaseModel]] = {
    m.__name__: m
    for m in (FilterBatchResult, DistilledProfile, CompanyNote, DraftResult, RevisionResult, FilterResult)
}
