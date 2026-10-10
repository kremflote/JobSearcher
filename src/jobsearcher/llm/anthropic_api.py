"""`anthropic_api` backend: the official `anthropic` SDK with an API key (ARCHITECTURE §8.1).

- Structured output via `output_config.format` (JSON schema), validated by the caller.
- Prompt caching: the system prompt and the shared context (profile) are cache breakpoints, so
  batches with the same profile pay ~10 % for that prefix.
- Research tools map to the server tools `web_search` / `web_fetch`.
"""

from __future__ import annotations

import json
import time
from typing import Any

from jobsearcher.llm.base import AgentRequest, AgentResponse, LLMError, Usage, output_json_schema
from jobsearcher.llm.costs import api_cost_usd

MODEL_IDS = {"fast": "claude-haiku-5-5", "balanced": "claude-sonnet-5-5", "best": "claude-opus-5-5"}

SERVER_TOOLS = {
    "web_search": {"type": "web_search_20260209", "name": "web_search", "max_uses": 8},
    "web_fetch": {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 8},
}

_CACHE = {"type": "ephemeral"}


class AnthropicApiBackend:
    name = "anthropic_api"

    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    def client(self) -> Any:
        if self._client is None:
            from jobsearcher.config import env

            key = env().anthropic_api_key
            if not key:
                raise LLMError("ANTHROPIC_API_KEY mangler i .env; anthropic_api kan ikke brukes.")
            import anthropic

            self._client = anthropic.Anthropic(api_key=key)
        return self._client

    def build_params(self, req: AgentRequest) -> dict[str, Any]:
        content: list[dict[str, Any]] = []
        if req.shared_context:
            content.append({"type": "text", "text": req.shared_context, "cache_control": _CACHE})
        content.append({"type": "text", "text": req.user_content})
        output_config: dict[str, Any] = {}
        if req.effort:
            output_config["effort"] = req.effort
        if req.output_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": output_json_schema(req.output_schema)}
        params: dict[str, Any] = {
            "model": MODEL_IDS[req.model_tier],
            "max_tokens": req.max_output_tokens,
            "system": [{"type": "text", "text": req.system_prompt, "cache_control": _CACHE}],
            "messages": [{"role": "user", "content": content}],
        }
        if output_config:
            params["output_config"] = output_config
        if req.tools:
            params["tools"] = [SERVER_TOOLS[t] for t in req.tools if t in SERVER_TOOLS]
        return params

    def run(self, req: AgentRequest) -> AgentResponse:
        from jobsearcher.config import load_settings

        timeout = req.timeout_s or load_settings().llm.timeout_s
        params = self.build_params(req)
        started = time.monotonic()
        try:
            msg = self.client().with_options(timeout=float(timeout)).messages.create(**params)
        except LLMError:
            raise
        except Exception as e:  # anthropic.APIError and transport errors
            raise LLMError(f"Anthropic API feilet: {e}") from e
        duration_ms = int((time.monotonic() - started) * 1000)

        if msg.stop_reason == "refusal":
            raise LLMError("Modellen avslo forespørselen (refusal).")
        if msg.stop_reason == "max_tokens":
            raise LLMError("Svaret ble kuttet (max_tokens).")
        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
        parsed = None
        if req.output_schema is not None:
            try:
                parsed = json.loads(text)
            except ValueError as e:
                raise LLMError(f"Ugyldig JSON fra API: {e}") from e

        u = msg.usage
        cache_write = int(getattr(u, "cache_creation_input_tokens", 0) or 0)
        cache_read = int(getattr(u, "cache_read_input_tokens", 0) or 0)
        uncached = int(u.input_tokens or 0)
        usage = Usage(
            input_tokens=uncached + cache_write + cache_read,
            output_tokens=int(u.output_tokens or 0),
            cache_creation_input_tokens=cache_write,
            cache_read_input_tokens=cache_read,
        )
        model = getattr(msg, "model", None) or params["model"]
        return AgentResponse(
            parsed=parsed,
            text=text,
            usage=usage,
            cost_usd=api_cost_usd(model, uncached, cache_write, cache_read, usage.output_tokens),
            model=model,
            duration_ms=duration_ms,
        )
