"""LLM layer: backends behind one protocol (ARCHITECTURE §8)."""

from jobsearcher.llm.base import (
    AgentRequest,
    AgentResponse,
    FallbackBackend,
    FallbackError,
    LLMBackend,
    LLMBackendError,
    LLMError,
    Usage,
    get_backend,
    output_json_schema,
)

__all__ = [
    "AgentRequest",
    "AgentResponse",
    "FallbackBackend",
    "FallbackError",
    "LLMBackend",
    "LLMBackendError",
    "LLMError",
    "Usage",
    "get_backend",
    "output_json_schema",
]
