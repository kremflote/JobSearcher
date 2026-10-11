"""OpenRouter backend and balance, with HTTP stubbed by httpx.MockTransport (no network)."""

from __future__ import annotations

import json

import httpx
import pytest

from jobsearcher.agents.schemas import FilterBatchResult
from jobsearcher.llm import AgentRequest, LLMBackendError, LLMError, output_json_schema
from jobsearcher.llm import openrouter
from jobsearcher.llm.openrouter import OpenRouterBackend, get_balance


def _req(**kw) -> AgentRequest:
    base = dict(
        agent="filter",
        system_prompt="Systemprompt æøå",
        shared_context="<profile_short>\nkort\n</profile_short>",
        user_content='<job_ad id="1">\nJunior utvikler\n</job_ad>',
        model_tier="fast",
        effort="low",
        output_schema=FilterBatchResult,
    )
    base.update(kw)
    return AgentRequest(**base)


def _completion(content, *, cost=0.0004, cached=100, model="deepseek/deepseek-v4.1-flash-20260910"):
    return {
        "id": "gen-1",
        "model": model,
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
        "usage": {
            "prompt_tokens": 1200,
            "completion_tokens": 300,
            "prompt_tokens_details": {"cached_tokens": cached},
            "cost": cost,
        },
    }


class Recorder:
    def __init__(self, *responses: httpx.Response | Exception):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def bodies(self):
        return [json.loads(r.content) for r in self.requests]


def _backend(rec: Recorder) -> OpenRouterBackend:
    return OpenRouterBackend(api_key="sk-or-test-not-real", transport=httpx.MockTransport(rec))


OK = json.dumps({"results": []})


def test_request_body_shape():
    rec = Recorder(httpx.Response(200, json=_completion(OK)))
    _backend(rec).run(_req())
    req = rec.requests[0]
    assert str(req.url) == "https://openrouter.ai/api/v1/chat/completions"
    assert req.headers["Authorization"] == "Bearer sk-or-test-not-real"
    body = rec.bodies()[0]
    assert body["model"] == "deepseek/deepseek-v4.1-flash"
    assert body["messages"][0] == {"role": "system", "content": "Systemprompt æøå"}
    assert body["messages"][1]["role"] == "user"
    assert body["messages"][1]["content"].startswith("<profile_short>")  # shared context first
    assert body["provider"] == {"require_parameters": True, "data_collection": "deny"}
    assert body["reasoning"] == {"effort": "low"}
    assert body["max_tokens"] == 16000
    fmt = body["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["name"] == "FilterBatchResult"
    assert fmt["json_schema"]["schema"] == output_json_schema(FilterBatchResult)
    assert "plugins" not in body


def test_research_tools_use_web_plugin_and_no_effort():
    rec = Recorder(httpx.Response(200, json=_completion(OK)))
    _backend(rec).run(_req(tools=["web_search", "web_fetch"], effort=None, model_tier="balanced"))
    body = rec.bodies()[0]
    assert body["plugins"] == [{"id": "web"}]
    assert "reasoning" not in body


def test_usage_cost_and_model_parsed():
    rec = Recorder(httpx.Response(200, json=_completion(OK)))
    resp = _backend(rec).run(_req())
    assert resp.parsed == {"results": []}
    assert resp.usage.input_tokens == 1200
    assert resp.usage.output_tokens == 300
    assert resp.usage.cache_read_input_tokens == 100
    assert resp.cost_usd == pytest.approx(0.0004)
    assert resp.model == "deepseek/deepseek-v4.1-flash-20260910"


def test_code_fenced_json_is_accepted():
    rec = Recorder(httpx.Response(200, json=_completion(f"```json\n{OK}\n```")))
    assert _backend(rec).run(_req()).parsed == {"results": []}


def test_invalid_json_retried_once_and_costs_summed():
    rec = Recorder(httpx.Response(200, json=_completion("ikke json")), httpx.Response(200, json=_completion(OK)))
    resp = _backend(rec).run(_req())
    assert len(rec.requests) == 2
    assert resp.parsed == {"results": []}
    assert resp.cost_usd == pytest.approx(0.0008)
    assert resp.usage.input_tokens == 2400


def test_invalid_json_twice_is_a_model_error():
    rec = Recorder(httpx.Response(200, json=_completion("nei")), httpx.Response(200, json=_completion(None)))
    with pytest.raises(LLMError, match="ugyldig JSON") as exc:
        _backend(rec).run(_req())
    assert not isinstance(exc.value, LLMBackendError)


@pytest.mark.parametrize(
    ("status", "match"),
    [
        (401, "avviste nøkkelen"),
        (402, "for lite kreditt"),
        (429, "for mange"),
        (502, "OpenRouter svarte 502: upstream nede"),
        (404, "No endpoints found"),
    ],
)
def test_http_errors_become_backend_errors(status, match):
    msg = "No endpoints found that can handle the requested parameters" if status == 404 else "upstream nede"
    rec = Recorder(httpx.Response(status, json={"error": {"code": status, "message": msg}}))
    with pytest.raises(LLMBackendError, match=match):
        _backend(rec).run(_req())


def test_error_in_200_body_and_timeout():
    rec = Recorder(httpx.Response(200, json={"error": {"message": "provider down"}}))
    with pytest.raises(LLMBackendError, match="provider down"):
        _backend(rec).run(_req())
    rec = Recorder(httpx.ReadTimeout("slow"))
    with pytest.raises(LLMBackendError, match="mer enn 300 s"):
        _backend(rec).run(_req())
    rec = Recorder(httpx.ConnectError("dns"))
    with pytest.raises(LLMBackendError, match="Kunne ikke nå"):
        _backend(rec).run(_req())


def test_missing_key():
    with pytest.raises(LLMBackendError, match="OPENROUTER_API_KEY"):
        OpenRouterBackend(transport=httpx.MockTransport(Recorder())).run(_req())


def test_unstructured_request_returns_text():
    rec = Recorder(httpx.Response(200, json=_completion("fritekst")))
    resp = _backend(rec).run(_req(output_schema=None))
    assert resp.parsed is None and resp.text == "fritekst"
    assert "response_format" not in rec.bodies()[0]


# --- balance -------------------------------------------------------------------------------


def _keys(monkeypatch, key="sk-or-test-not-real", mgmt=""):
    from jobsearcher.config import env

    monkeypatch.setenv("OPENROUTER_API_KEY", key)
    monkeypatch.setenv("OPENROUTER_MANAGEMENT_KEY", mgmt)
    env.cache_clear()


def test_balance_not_configured():
    b = get_balance(transport=httpx.MockTransport(Recorder()))
    assert b.configured is False and b.balance_usd is None and b.balance_source is None


def test_balance_from_account_with_management_key(monkeypatch):
    _keys(monkeypatch, mgmt="sk-or-mgmt-test")
    rec = Recorder(httpx.Response(200, json={"data": {"total_credits": 10.0, "total_usage": 2.6}}))
    b = get_balance(transport=httpx.MockTransport(rec))
    assert str(rec.requests[0].url) == "https://openrouter.ai/api/v1/credits"
    assert rec.requests[0].headers["Authorization"] == "Bearer sk-or-mgmt-test"
    assert (b.configured, b.balance_source) == (True, "account")
    assert b.balance_usd == pytest.approx(7.4)
    assert b.total_credits_usd == 10.0 and b.used_usd == pytest.approx(2.6)
    assert b.fetched_at is not None


def test_balance_from_key_limit(monkeypatch):
    _keys(monkeypatch)
    rec = Recorder(httpx.Response(200, json={"data": {"limit": 5.0, "limit_remaining": 4.25, "usage": 0.75}}))
    b = get_balance(transport=httpx.MockTransport(rec))
    assert str(rec.requests[0].url) == "https://openrouter.ai/api/v1/key"
    assert (b.balance_source, b.balance_usd, b.total_credits_usd, b.used_usd) == ("key_limit", 4.25, 5.0, 0.75)


def test_balance_unknown_when_key_has_no_limit(monkeypatch):
    _keys(monkeypatch)
    rec = Recorder(httpx.Response(200, json={"data": {"limit": None, "limit_remaining": None, "usage": 0.1}}))
    b = get_balance(transport=httpx.MockTransport(rec))
    assert b.configured is True and b.balance_usd is None and b.balance_source is None
    assert b.used_usd == pytest.approx(0.1)
    assert b.fetched_at is not None


@pytest.mark.parametrize("failure", [httpx.ConnectError("offline"), httpx.Response(500, text="nede"),
                                     httpx.Response(200, text="ikke json")])
def test_balance_failure_never_raises(monkeypatch, failure):
    _keys(monkeypatch)
    b = get_balance(transport=httpx.MockTransport(Recorder(failure)))
    assert b.configured is True
    assert b.balance_usd is None and b.balance_source is None and b.fetched_at is None


def test_balance_cached_ten_minutes(monkeypatch):
    _keys(monkeypatch)
    clock = [1000.0]
    monkeypatch.setattr(openrouter.time, "monotonic", lambda: clock[0])
    rec = Recorder(
        httpx.Response(200, json={"data": {"limit": 5.0, "limit_remaining": 4.0}}),
        httpx.Response(200, json={"data": {"limit": 5.0, "limit_remaining": 3.0}}),
    )
    transport = httpx.MockTransport(rec)
    assert get_balance(transport=transport).balance_usd == 4.0
    clock[0] += 599
    assert get_balance(transport=transport).balance_usd == 4.0
    assert len(rec.requests) == 1
    clock[0] += 2
    assert get_balance(transport=transport).balance_usd == 3.0
    assert len(rec.requests) == 2
