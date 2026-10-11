"""LLM backends: claude_code (subprocess mocked), mock, factory, costs. OpenRouter: test_openrouter.py."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime

import pytest

from jobsearcher.agents.schemas import DistilledProfile, FilterBatchResult
from jobsearcher.db.models import AgentRun
from jobsearcher.llm import AgentRequest, LLMBackendError, LLMError, get_backend, output_json_schema
from jobsearcher.llm import claude_code
from jobsearcher.llm.costs import cost_status, month_cost_usd
from jobsearcher.llm.mock import MockBackend


def _req(**kw) -> AgentRequest:
    base = dict(
        agent="filter",
        system_prompt="Systemprompt æøå",
        shared_context="<profile_short>\nkort\n</profile_short>",
        user_content='<job_ad id="1" prefiltered="false">\n<text>\nJunior utvikler\n</text>\n</job_ad>',
        model_tier="fast",
        effort="low",
        output_schema=FilterBatchResult,
    )
    base.update(kw)
    return AgentRequest(**base)


# --- schema ------------------------------------------------------------------------------


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def test_output_schema_is_strict_and_inlined():
    schema = output_json_schema(FilterBatchResult)
    text = json.dumps(schema)
    assert "$ref" not in text and "$defs" not in text
    for node in _walk(schema):
        assert "maximum" not in node and "title" not in node
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])


# --- claude_code -------------------------------------------------------------------------

CLI_OK = {
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "duration_ms": 1200,
    "total_cost_usd": 0.0012,
    "usage": {"input_tokens": 10, "cache_creation_input_tokens": 1500, "cache_read_input_tokens": 100,
              "output_tokens": 300},
    "modelUsage": {"claude-haiku-5-5": {}},
    "result": "",
    "structured_output": {"results": []},
}


def test_build_command_isolates_the_call(tmp_path):
    cmd = claude_code.build_command(_req(max_budget_usd=0.5), "claude", tmp_path / "p.md")
    joined = " ".join(cmd)
    for flag in ("-p", "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"):
        assert flag in cmd
    assert cmd[cmd.index("--model") + 1] == "haiku"
    assert cmd[cmd.index("--tools") + 1] == ""
    assert cmd[cmd.index("--setting-sources") + 1] == ""
    assert cmd[cmd.index("--effort") + 1] == "low"
    assert cmd[cmd.index("--max-budget-usd") + 1] == "0.5"
    assert json.loads(cmd[cmd.index("--json-schema") + 1])["type"] == "object"
    assert "--allowedTools" not in joined


def test_build_command_with_research_tools(tmp_path):
    cmd = claude_code.build_command(_req(tools=["web_search", "web_fetch"], model_tier="balanced"), "c", tmp_path)
    assert cmd[cmd.index("--tools") + 1] == "WebSearch,WebFetch"
    assert cmd[cmd.index("--allowedTools") + 1] == "WebSearch,WebFetch"
    assert cmd[cmd.index("--model") + 1] == "sonnet"


def test_parse_result_usage_and_cost():
    resp = claude_code.parse_result(CLI_OK, structured=True, fallback_model="haiku")
    assert resp.parsed == {"results": []}
    assert resp.usage.input_tokens == 1610
    assert resp.usage.cache_creation_input_tokens == 1500
    assert resp.cost_usd == pytest.approx(0.0012)
    assert resp.model == "claude-haiku-5-5"


def test_parse_result_error_raises():
    with pytest.raises(LLMError, match="budget"):
        claude_code.parse_result(
            {"is_error": True, "subtype": "error_max_budget_usd", "result": None}, structured=True, fallback_model="x"
        )


@pytest.mark.parametrize(
    ("data", "backend_error"),
    [
        ({"is_error": True, "subtype": "success", "result": "Claude AI usage limit reached|1760000000"}, True),
        ({"is_error": True, "subtype": "success", "result": "Invalid API key · Please run /login"}, True),
        ({"is_error": True, "subtype": "error_during_execution", "result": None}, True),
        ({"is_error": True, "subtype": "error_max_budget_usd", "result": None}, False),
        ({"is_error": True, "subtype": "error_max_structured_output_retries", "result": None}, False),
    ],
)
def test_parse_result_error_classification(data, backend_error):
    with pytest.raises(LLMError) as exc:
        claude_code.parse_result(data, structured=True, fallback_model="x")
    assert isinstance(exc.value, LLMBackendError) is backend_error


def test_missing_structured_output_is_not_a_backend_error():
    data = dict(CLI_OK, structured_output=None, result="ikke json")
    with pytest.raises(LLMError) as exc:
        claude_code.parse_result(data, structured=True, fallback_model="x")
    assert not isinstance(exc.value, LLMBackendError)


def test_cli_not_found_is_a_backend_error(monkeypatch, tmp_path):
    monkeypatch.setattr(claude_code.shutil, "which", lambda _: None)
    monkeypatch.setattr(claude_code, "FALLBACK_CLI", tmp_path / "nope.exe")
    with pytest.raises(LLMBackendError, match="Fant ikke"):
        claude_code.find_cli()


def test_run_strips_api_key_and_uses_sandbox(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    seen = {}

    def fake_run(cmd, **kw):
        seen.update(kw, cmd=cmd)
        prompt_file = cmd[cmd.index("--system-prompt-file") + 1]
        with open(prompt_file, encoding="utf-8") as f:
            seen["system"] = f.read()
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(CLI_OK), stderr="")

    monkeypatch.setattr(claude_code.subprocess, "run", fake_run)
    backend = claude_code.ClaudeCodeBackend(cli="claude", sandbox_dir=tmp_path / "sandbox")
    resp = backend.run(_req())
    assert resp.parsed == {"results": []}
    assert "ANTHROPIC_API_KEY" not in seen["env"]
    assert seen["cwd"] == tmp_path / "sandbox"
    assert seen["input"].startswith("<profile_short>") and "<job_ad id=\"1\"" in seen["input"]
    assert seen["system"] == "Systemprompt æøå"
    assert seen["encoding"] == "utf-8"
    assert seen["timeout"] == 600  # settings.llm.timeout_s


def test_run_timeout_becomes_llm_error(monkeypatch, tmp_path):
    def fake_run(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 1)

    monkeypatch.setattr(claude_code.subprocess, "run", fake_run)
    with pytest.raises(LLMBackendError, match="mer enn"):
        claude_code.ClaudeCodeBackend(cli="claude", sandbox_dir=tmp_path).run(_req(timeout_s=1))


# --- mock & factory ----------------------------------------------------------------------


def test_mock_outputs_validate():
    backend = MockBackend()
    out = backend.run(_req())
    batch = FilterBatchResult.model_validate(out.parsed)
    assert [r.job_id for r in batch.results] == ["1"]
    assert batch.results[0].seniority == "entry"
    DistilledProfile.model_validate(backend.run(_req(output_schema=DistilledProfile)).parsed)


def test_get_backend_by_name():
    assert get_backend("mock").name == "mock"
    assert get_backend("claude_code").name == "claude_code"
    assert get_backend("openrouter").name == "openrouter"
    with pytest.raises(ValueError):
        get_backend("nope")


# --- costs -------------------------------------------------------------------------------


def _run(cost, created_at):
    return AgentRun(agent="filter", backend="mock", model="m", prompt_version="1", cost_usd=cost,
                    created_at=created_at)


def test_month_cost_and_status(session):
    now = datetime(2026, 10, 15, tzinfo=UTC)
    session.add(_run(5.0, datetime(2026, 10, 2, tzinfo=UTC)))
    session.add(_run(16.0, datetime(2026, 10, 14, tzinfo=UTC)))
    session.add(_run(99.0, datetime(2026, 9, 30, 21, 0, tzinfo=UTC)))  # 23:00 Oslo, September
    session.commit()
    assert month_cost_usd(session, now) == pytest.approx(21.0)
    session.add(_run(1.0, datetime(2026, 9, 30, 22, 30, tzinfo=UTC)))  # 00:30 Oslo, October
    session.commit()
    assert month_cost_usd(session, now) == pytest.approx(22.0)
    spent, cap, warn = cost_status(session, now)
    assert (spent, cap, warn) == (pytest.approx(22.0), 10, True)
