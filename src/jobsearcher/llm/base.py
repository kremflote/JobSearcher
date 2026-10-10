"""LLM backend protocol and request/response types (ARCHITECTURE §8.1).

Backends are thin: they send one request and return the raw JSON output plus usage and cost.
Validation against the Pydantic schema, retries and agent_runs bookkeeping live in
`jobsearcher.agents.base`.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel

Tier = Literal["fast", "balanced", "best"]
TIERS: tuple[str, ...] = ("fast", "balanced", "best")


class LLMError(RuntimeError):
    """The backend could not produce a response (process error, timeout, API error, refusal)."""


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


def get_backend(name: str | None = None) -> LLMBackend:
    """Backend by name (`claude_code` | `anthropic_api` | `mock`); default from settings.llm.backend."""
    if name is None:
        from jobsearcher.config import load_settings

        name = load_settings().llm.backend
    if name == "claude_code":
        from jobsearcher.llm.claude_code import ClaudeCodeBackend

        return ClaudeCodeBackend()
    if name == "anthropic_api":
        from jobsearcher.llm.anthropic_api import AnthropicApiBackend

        return AnthropicApiBackend()
    if name == "mock":
        from jobsearcher.llm.mock import MockBackend

        return MockBackend()
    raise ValueError(f"Unknown LLM backend: {name!r}")
