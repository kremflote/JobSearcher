"""LLM layer: backends behind one protocol (ARCHITECTURE §8)."""

from jobsearcher.llm.base import (
    AgentRequest,
    AgentResponse,
    LLMBackend,
    LLMError,
    Usage,
    get_backend,
    output_json_schema,
)

__all__ = [
    "AgentRequest",
    "AgentResponse",
    "LLMBackend",
    "LLMError",
    "Usage",
    "get_backend",
    "output_json_schema",
]
