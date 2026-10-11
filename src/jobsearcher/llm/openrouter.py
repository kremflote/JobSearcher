"""`openrouter` backend: OpenRouter's OpenAI-compatible API (ARCHITECTURE §8.1, spike 05).

- Structured output via `response_format: json_schema` (strict); the caller validates against
  the Pydantic schema. Invalid JSON is retried once here.
- `provider.require_parameters` routes only to endpoints that support the schema;
  `provider.data_collection: deny` excludes providers that store or train on the data.
- The shared context (profile) goes first in the user message so provider prompt caching hits.
- Cost is the real `usage.cost` from the response.

`get_balance()` reads the credit balance for the usage card (FRONTEND §5.1), cached 10 minutes.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from jobsearcher.llm.base import (
    AgentRequest,
    AgentResponse,
    LLMBackendError,
    LLMError,
    Usage,
    output_json_schema,
)

log = logging.getLogger(__name__)

BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"
WEB_TOOLS = frozenset({"web_search", "web_fetch"})
# OpenRouter's reasoning.effort takes minimal | low | medium | high.
EFFORT = {"minimal": "minimal", "low": "low", "medium": "medium", "high": "high", "xhigh": "high", "max": "high"}
_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.S)


def _api_key() -> str:
    from jobsearcher.config import env

    return env().openrouter_api_key


def _error_detail(resp: httpx.Response) -> str:
    try:
        data = resp.json()
        msg = (data.get("error") or {}).get("message") if isinstance(data, dict) else None
    except ValueError:
        msg = None
    return (msg or resp.text or "").strip()[:300]


def _http_error(resp: httpx.Response) -> LLMBackendError:
    code = resp.status_code
    if code == 401:
        return LLMBackendError("OpenRouter avviste nøkkelen (401). Sjekk OPENROUTER_API_KEY i .env.")
    if code == 402:
        return LLMBackendError("OpenRouter: for lite kreditt (402). Fyll på kontoen på openrouter.ai.")
    if code == 429:
        return LLMBackendError("OpenRouter: for mange forespørsler (429). Prøv igjen senere.")
    return LLMBackendError(f"OpenRouter svarte {code}: {_error_detail(resp)}")


def parse_content(content: Any) -> dict[str, Any] | None:
    """The message content as a JSON object, or None if it is not one (code fences tolerated)."""
    if isinstance(content, list):  # content parts
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    if not isinstance(content, str):
        return None
    m = _FENCE.match(content)
    if m:
        content = m.group(1)
    try:
        parsed = json.loads(content)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def parse_usage(data: dict[str, Any]) -> tuple[Usage, float]:
    u = data.get("usage") or {}
    cached = int((u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
    usage = Usage(
        input_tokens=int(u.get("prompt_tokens") or 0),
        output_tokens=int(u.get("completion_tokens") or 0),
        cache_read_input_tokens=cached,
    )
    return usage, float(u.get("cost") or 0.0)


class OpenRouterBackend:
    name = "openrouter"

    def __init__(self, api_key: str | None = None, transport: httpx.BaseTransport | None = None) -> None:
        self._api_key = api_key
        self._transport = transport

    def build_body(self, req: AgentRequest) -> dict[str, Any]:
        from jobsearcher.config import load_settings

        models = load_settings().llm.openrouter.models
        body: dict[str, Any] = {
            "model": models.get(req.model_tier, DEFAULT_MODEL),
            "messages": [
                {"role": "system", "content": req.system_prompt},
                {"role": "user", "content": req.full_user_content()},
            ],
            "max_tokens": req.max_output_tokens,
            "provider": {"require_parameters": True, "data_collection": "deny"},
        }
        if req.output_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": req.output_schema.__name__,
                    "strict": True,
                    "schema": output_json_schema(req.output_schema),
                },
            }
        if req.effort:
            body["reasoning"] = {"effort": EFFORT.get(req.effort, "medium")}
        if WEB_TOOLS.intersection(req.tools):
            body["plugins"] = [{"id": "web"}]
        return body

    def _post(self, body: dict[str, Any], key: str, timeout: float) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {key}", "X-Title": "JobSearcher"}
        try:
            with httpx.Client(transport=self._transport, timeout=timeout) as client:
                resp = client.post(f"{BASE_URL}/chat/completions", json=body, headers=headers)
        except httpx.TimeoutException as e:
            raise LLMBackendError(f"OpenRouter brukte mer enn {timeout:g} s") from e
        except httpx.HTTPError as e:
            raise LLMBackendError(f"Kunne ikke nå OpenRouter: {e}") from e
        if resp.status_code >= 400:
            raise _http_error(resp)
        try:
            data = resp.json()
        except ValueError as e:
            raise LLMBackendError("OpenRouter ga et svar som ikke er JSON") from e
        if not isinstance(data, dict):
            raise LLMBackendError("OpenRouter ga et uventet svar")
        if data.get("error"):
            msg = (data["error"] or {}).get("message") if isinstance(data["error"], dict) else data["error"]
            raise LLMBackendError(f"OpenRouter feilet: {str(msg)[:300]}")
        return data

    def run(self, req: AgentRequest) -> AgentResponse:
        from jobsearcher.config import load_settings

        key = self._api_key if self._api_key is not None else _api_key()
        if not key:
            raise LLMBackendError("OPENROUTER_API_KEY mangler i .env; openrouter kan ikke brukes.")
        timeout = float(load_settings().llm.openrouter.timeout_s)
        body = self.build_body(req)
        structured = req.output_schema is not None

        usage = Usage()
        cost = 0.0
        started = time.monotonic()
        parsed: dict[str, Any] | None = None
        text: str | None = None
        model = body["model"]
        for attempt in range(2):
            data = self._post(body, key, timeout)
            u, c = parse_usage(data)
            usage, cost = usage + u, cost + c
            model = data.get("model") or model
            choices = data.get("choices") or []
            message = (choices[0].get("message") or {}) if choices else {}
            content = message.get("content")
            text = content if isinstance(content, str) else None
            if not structured:
                break
            parsed = parse_content(content)
            if parsed is not None:
                break
            log.warning("openrouter returned invalid JSON", extra={"data": {"agent": req.agent, "attempt": attempt}})
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if structured and parsed is None:
            raise LLMError("OpenRouter ga ugyldig JSON to ganger")

        log.info(
            "openrouter call",
            extra={
                "data": {
                    "agent": req.agent,
                    "model": model,
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "cost_usd": cost,
                    "wall_ms": elapsed_ms,
                }
            },
        )
        return AgentResponse(
            parsed=parsed if structured else None,
            text=text,
            usage=usage,
            cost_usd=round(cost, 6),
            model=model,
            duration_ms=elapsed_ms,
        )


# --- Balance ---------------------------------------------------------------------------------

BALANCE_TTL_S = 10 * 60
BALANCE_TIMEOUT_S = 5.0


@dataclass
class Balance:
    """Fields of `api.schemas.OpenRouterBalance`."""

    configured: bool
    balance_usd: float | None = None
    total_credits_usd: float | None = None
    used_usd: float | None = None
    balance_source: str | None = None  # account | key_limit
    fetched_at: datetime | None = None


_balance_cache: tuple[float, Balance] | None = None


def clear_balance_cache() -> None:
    global _balance_cache
    _balance_cache = None


def _num(v: Any) -> float | None:
    return None if v is None else float(v)


def _fetch_balance(transport: httpx.BaseTransport | None) -> Balance:
    from jobsearcher.config import env

    key = env().openrouter_api_key
    mgmt = env().openrouter_management_key
    if not key:
        return Balance(configured=False)
    try:
        with httpx.Client(transport=transport, timeout=BALANCE_TIMEOUT_S) as client:
            if mgmt:
                r = client.get(f"{BASE_URL}/credits", headers={"Authorization": f"Bearer {mgmt}"})
                r.raise_for_status()
                d = r.json()["data"]
                total = float(d["total_credits"])
                return Balance(
                    configured=True,
                    balance_usd=round(total - float(d["total_usage"]), 6),
                    total_credits_usd=total,
                    used_usd=round(float(d["total_usage"]), 6),
                    balance_source="account",
                    fetched_at=datetime.now(UTC),
                )
            r = client.get(f"{BASE_URL}/key", headers={"Authorization": f"Bearer {key}"})
            r.raise_for_status()
            d = r.json()["data"]
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
        log.warning("openrouter balance unavailable", extra={"data": {"error": str(e)[:300]}})
        return Balance(configured=True)
    now = datetime.now(UTC)
    if d.get("limit") is None or d.get("limit_remaining") is None:
        return Balance(configured=True, used_usd=_num(d.get("usage")), fetched_at=now)
    return Balance(
        configured=True,
        balance_usd=_num(d["limit_remaining"]),
        total_credits_usd=_num(d["limit"]),
        used_usd=_num(d.get("usage")),
        balance_source="key_limit",
        fetched_at=now,
    )


def get_balance(transport: httpx.BaseTransport | None = None) -> Balance:
    """OpenRouter credit balance (ARCHITECTURE §8.1). Never raises; cached `BALANCE_TTL_S`."""
    global _balance_cache
    now = time.monotonic()
    if _balance_cache is not None and now - _balance_cache[0] < BALANCE_TTL_S:
        return _balance_cache[1]
    balance = _fetch_balance(transport)
    _balance_cache = (now, balance)
    return balance
