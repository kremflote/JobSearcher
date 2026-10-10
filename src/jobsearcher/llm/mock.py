"""`mock` backend: deterministic, schema-valid outputs without any LLM (ARCHITECTURE §8.1).

Used by tests and by dashboard development with `llm.backend: mock`. Tests can pass a
`responder` to script specific outputs (e.g. invalid output to exercise the retry).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from typing import Any

from jobsearcher.llm.base import AgentRequest, AgentResponse, Usage, output_json_schema

_JOB_AD = re.compile(r'<job_ad id="([^"]+)"([^>]*)>(.*?)</job_ad>', re.S)


def _stable_int(text: str, mod: int) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % mod


def _filter_batch(req: AgentRequest) -> dict[str, Any]:
    results = []
    for job_id, attrs, body in _JOB_AD.findall(req.user_content):
        lower = body.lower()
        prefiltered = 'prefiltered="true"' in attrs
        if prefiltered or "junior" in lower or "nyutdannet" in lower or "graduate" in lower:
            seniority = "entry"
        elif "erfaren" in lower or "experienced" in lower or "års erfaring" in lower:
            seniority = "experienced"
        else:
            seniority = "unspecified"
        job_type = "trainee" if "trainee" in lower else "summer" if "sommer" in lower else "unknown"
        results.append(
            {
                "job_id": job_id,
                "score": 40 + _stable_int(job_id, 60),
                "confidence": "low" if "annonseteksten mangler" in lower else "high",
                "role_category": "fullstack",
                "job_type": job_type,
                "seniority": seniority,
                "tech": ["python"],
                "summary": "Mock-sammendrag av stillingen.",
                "key_requirements": ["Mock-krav"],
                "match_reasons": ["Mock-treff"],
                "concerns": [],
                "deadline": None,
                "deadline_text": None,
                "contacts": [],
                "application_url": None,
                "ad_language": "en" if " the " in lower else "no",
            }
        )
    return {"results": results}


def _distilled(req: AgentRequest) -> dict[str, Any]:
    digest = hashlib.sha256(req.full_user_content().encode("utf-8")).hexdigest()[:8]
    return {
        "profile_short": f"# Kortprofil (mock {digest})\n\nNyutdannet utvikler.",
        "profile_long": f"# Lang profil (mock {digest})\n\nNyutdannet utvikler med flere prosjekter.",
        "voice": f"# Stemme (mock {digest})\n\nKorte setninger, uformell tone.",
    }


def _from_schema(schema: dict[str, Any]) -> Any:
    """Minimal instance of a (strict, inlined) JSON schema."""
    if "anyOf" in schema:
        options = schema["anyOf"]
        if any(o.get("type") == "null" for o in options):
            return None
        return _from_schema(options[0])
    if "enum" in schema:
        return schema["enum"][0]
    if "const" in schema:
        return schema["const"]
    t = schema.get("type")
    if t == "object":
        return {k: _from_schema(v) for k, v in schema.get("properties", {}).items()}
    if t == "array":
        return []
    if t == "string":
        return "mock"
    if t == "integer":
        return 0
    if t == "number":
        return 0.0
    if t == "boolean":
        return False
    return None


BUILTIN: dict[str, Callable[[AgentRequest], dict[str, Any]]] = {
    "FilterBatchResult": _filter_batch,
    "DistilledProfile": _distilled,
}


class MockBackend:
    name = "mock"

    def __init__(
        self,
        responder: Callable[[AgentRequest], dict[str, Any] | str] | None = None,
        cost_usd: float = 0.0,
    ) -> None:
        self.responder = responder
        self.cost_usd = cost_usd
        self.requests: list[AgentRequest] = []

    def run(self, req: AgentRequest) -> AgentResponse:
        self.requests.append(req)
        out: dict[str, Any] | str | None
        if self.responder is not None:
            out = self.responder(req)
        elif req.output_schema is not None:
            builder = BUILTIN.get(req.output_schema.__name__)
            out = builder(req) if builder else _from_schema(output_json_schema(req.output_schema))
        else:
            out = "mock"
        content = req.full_user_content()
        usage = Usage(input_tokens=(len(req.system_prompt) + len(content)) // 4, output_tokens=200)
        return AgentResponse(
            parsed=out if isinstance(out, dict) else None,
            text=out if isinstance(out, str) else None,
            usage=usage,
            cost_usd=self.cost_usd,
            model=f"mock-{req.model_tier}",
            duration_ms=1,
        )
