"""LLM backend protocol and request/response types (ARCHITECTURE §8.1).

Backends are thin: they send one request and return the raw JSON output plus usage and cost.
Validation against the Pydantic schema, retries and agent_runs bookkeeping live in
`jobsearcher.agents.base`.
"""

from __future__ import annotations

import copy
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel

log = logging.getLogger(__name__)

Tier = Literal["fast", "balanced", "best"]
TIERS: tuple[str, ...] = ("fast", "balanced", "best")


class LLMError(RuntimeError):
    """The backend could not produce a response (process error, timeout, API error, refusal)."""


class LLMBackendError(LLMError):
    """The backend itself is unavailable: CLI missing, login expired, usage limit, timeout,
    process or transport error. Only these trigger the fallback (ARCHITECTURE §8.1); model-level
    failures (invalid or missing structured output, per-call budget) stay plain `LLMError`.
    """


class FallbackError(LLMError):
    """The fallback backend failed too (or was used directly while the circuit breaker is open)."""

    def __init__(self, message: str, *, backend: str, fallback_from: str, primary_error: str | None,
                 primary_duration_ms: int = 0) -> None:
        super().__init__(message)
        self.backend = backend
        self.fallback_from = fallback_from
        self.primary_error = primary_error
        self.primary_duration_ms = primary_duration_ms


@dataclass
class Usage:
    """Token usage. `input_tokens` is the total input (uncached + cache write + cache read)."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.cache_creation_input_tokens + other.cache_creation_input_tokens,
            self.cache_read_input_tokens + other.cache_read_input_tokens,
        )


@dataclass
class AgentRequest:
    """One LLM call.

    `shared_context` is the part that is identical across calls (profile, preferences). The API
    backend marks it for prompt caching; the CLI backend sends it first in the same message.
    `user_content` is the per-call part (ads, instructions).
    """

    agent: str
    system_prompt: str
    user_content: str
    model_tier: Tier = "fast"
    shared_context: str = ""
    effort: str | None = None
    output_schema: type[BaseModel] | None = None
    tools: list[str] = field(default_factory=list)
    max_budget_usd: float | None = None
    timeout_s: int | None = None
    max_output_tokens: int = 16000

    def full_user_content(self) -> str:
        if self.shared_context:
            return f"{self.shared_context}\n\n{self.user_content}"
        return self.user_content


@dataclass
class AgentResponse:
    parsed: dict[str, Any] | None
    """Structured output (raw JSON object) when an output schema was given."""
    text: str | None
    usage: Usage
    cost_usd: float
    model: str
    duration_ms: int
    backend: str | None = None
    """Backend that answered; set by `FallbackBackend` (None = the backend that was called)."""
    fallback_from: str | None = None
    """Primary backend this call fell back from."""
    primary_error: str | None = None
    """Error of the failed primary attempt (None when the circuit breaker skipped it)."""
    primary_duration_ms: int = 0


class LLMBackend(Protocol):
    name: str

    def run(self, req: AgentRequest) -> AgentResponse: ...


# --- JSON schema for structured output -------------------------------------------------

_DROP_KEYS = {
    "title",
    "default",
    "examples",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "maxItems",
    "minItems",
    "pattern",
}


def output_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """A strict, self-contained JSON schema for structured output.

    Inlines `$ref`s, drops keywords structured output does not support (bounds are enforced by
    the Pydantic validators instead), sets `additionalProperties: false` and marks every
    property required (nullable fields stay nullable).
    """
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, list):
            return [walk(n) for n in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            name = node["$ref"].rsplit("/", 1)[-1]
            return walk(copy.deepcopy(defs[name]))
        out = {k: walk(v) for k, v in node.items() if k not in _DROP_KEYS}
        if out.get("type") == "object" and "properties" in out:
            out["additionalProperties"] = False
            out["required"] = list(out["properties"].keys())
        return out

    return walk(raw)


# --- Fallback (ARCHITECTURE §8.1) ---------------------------------------------------------

BREAKER_S = 30 * 60
"""After a primary backend failure, skip the primary for this long (in-process)."""

_breaker_until: dict[str, float] = {}


def reset_breaker() -> None:
    _breaker_until.clear()


def breaker_open(name: str) -> bool:
    return _breaker_until.get(name, 0.0) > time.monotonic()


class FallbackBackend:
    """Runs the primary backend and, on a backend error, the same request once on the fallback.

    A primary failure opens a circuit breaker: for `BREAKER_S` seconds calls go straight to the
    fallback, so a batch does not wait out a timeout per call.
    """

    def __init__(self, primary: LLMBackend, fallback: LLMBackend) -> None:
        self.primary = primary
        self.fallback = fallback
        self.name = primary.name

    def run(self, req: AgentRequest) -> AgentResponse:
        primary_error: str | None = None
        primary_ms = 0
        if not breaker_open(self.primary.name):
            started = time.monotonic()
            try:
                resp = self.primary.run(req)
            except LLMBackendError as e:
                primary_error = str(e)
                primary_ms = int((time.monotonic() - started) * 1000)
                _breaker_until[self.primary.name] = time.monotonic() + BREAKER_S
                log.warning(
                    "primary LLM backend failed, using fallback",
                    extra={"data": {"primary": self.primary.name, "fallback": self.fallback.name,
                                    "error": primary_error[:500]}},
                )
            else:
                resp.backend = resp.backend or self.primary.name
                return resp
        try:
            resp = self.fallback.run(req)
        except LLMError as e:
            raise FallbackError(
                str(e), backend=self.fallback.name, fallback_from=self.primary.name,
                primary_error=primary_error, primary_duration_ms=primary_ms,
            ) from e
        resp.backend = self.fallback.name
        resp.fallback_from = self.primary.name
        resp.primary_error = primary_error
        resp.primary_duration_ms = primary_ms
        return resp


def _make_backend(name: str) -> LLMBackend:
    if name == "claude_code":
        from jobsearcher.llm.claude_code import ClaudeCodeBackend

        return ClaudeCodeBackend()
    if name == "openrouter":
        from jobsearcher.llm.openrouter import OpenRouterBackend

        return OpenRouterBackend()
    if name == "mock":
        from jobsearcher.llm.mock import MockBackend

        return MockBackend()
    raise ValueError(f"Unknown LLM backend: {name!r}")


def get_backend(name: str | None = None, *, fallback: bool = True) -> LLMBackend:
    """Backend by name (`claude_code` | `openrouter` | `mock`); default from settings.llm.backend.

    With `fallback` (default) and `llm.fallback` set to another backend, the primary is wrapped
    in `FallbackBackend`. An `openrouter` fallback needs `OPENROUTER_API_KEY`; without it the
    fallback is off.
    """
    from jobsearcher.config import env
    from jobsearcher.db.repo import current_settings

    llm = current_settings().llm
    name = name or llm.backend
    primary = _make_backend(name)
    fb = llm.fallback_backend
    if not fallback or fb is None or fb == name or name == "mock":
        return primary
    if fb == "openrouter" and not env().openrouter_api_key:
        return primary
    return FallbackBackend(primary, _make_backend(fb))
