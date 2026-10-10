"""`claude_code` backend: headless Claude Code (`claude -p`) on the user's subscription.

ARCHITECTURE §8.1, spike 02. Each call is isolated so it carries ~1.5k tokens of overhead
instead of ~39k (Claude Code's default prompt, the user's MCP servers, hooks, skills, CLAUDE.md):

- `--system-prompt-file` replaces Claude Code's system prompt
- `--tools ""` removes all built-in tools (the research agent gets an explicit list)
- `--strict-mcp-config` without `--mcp-config` loads no MCP servers
- `--setting-sources ""` ignores user/project/local settings (hooks, plugins, permissions)
- `--disable-slash-commands` drops skills
- cwd is the empty `DATA_DIR/llm_sandbox`, so no CLAUDE.md is discovered
- `--no-session-persistence` writes no transcript
- `ANTHROPIC_API_KEY` is removed from the child env so the subscription login is used
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from jobsearcher.llm.base import AgentRequest, AgentResponse, LLMError, Usage, output_json_schema

log = logging.getLogger(__name__)

FALLBACK_CLI = Path.home() / ".local" / "bin" / ("claude.exe" if os.name == "nt" else "claude")

MODEL_ALIASES = {"fast": "haiku", "balanced": "sonnet", "best": "opus"}

TOOL_NAMES = {"web_search": "WebSearch", "web_fetch": "WebFetch"}


def find_cli() -> str:
    found = shutil.which("claude")
    if found:
        return found
    if FALLBACK_CLI.exists():
        return str(FALLBACK_CLI)
    raise LLMError("Fant ikke `claude` CLI. Installer Claude Code eller bytt llm.backend.")


def child_env() -> dict[str, str]:
    """Environment for the subprocess: no API key (subscription wins), optional OAuth token."""
    from jobsearcher.config import env

    child = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    token = env().claude_code_oauth_token
    if token and "CLAUDE_CODE_OAUTH_TOKEN" not in child:
        child["CLAUDE_CODE_OAUTH_TOKEN"] = token
    return child


def build_command(req: AgentRequest, cli: str, system_prompt_file: Path) -> list[str]:
    cmd = [
        cli,
        "-p",
        "--output-format",
        "json",
        "--model",
        MODEL_ALIASES[req.model_tier],
        "--system-prompt-file",
        str(system_prompt_file),
        "--strict-mcp-config",
        "--setting-sources",
        "",
        "--disable-slash-commands",
        "--no-session-persistence",
        "--permission-prompts",
        "none",
    ]
    tools = [TOOL_NAMES.get(t, t) for t in req.tools]
    if tools:
        cmd += ["--tools", ",".join(tools), "--allowedTools", ",".join(tools)]
    else:
        cmd += ["--tools", ""]
    if req.effort:
        cmd += ["--effort", req.effort]
    if req.max_budget_usd:
        cmd += ["--max-budget-usd", f"{req.max_budget_usd:g}"]
    if req.output_schema is not None:
        cmd += ["--json-schema", json.dumps(output_json_schema(req.output_schema), ensure_ascii=False)]
    return cmd


def parse_result(data: dict[str, Any], *, structured: bool, fallback_model: str) -> AgentResponse:
    if data.get("is_error") or data.get("subtype") not in (None, "success"):
        detail = data.get("result") or data.get("subtype") or "ukjent feil"
        raise LLMError(f"claude -p feilet: {detail}")
    u = data.get("usage") or {}
    cache_write = int(u.get("cache_creation_input_tokens") or 0)
    cache_read = int(u.get("cache_read_input_tokens") or 0)
    usage = Usage(
        input_tokens=int(u.get("input_tokens") or 0) + cache_write + cache_read,
        output_tokens=int(u.get("output_tokens") or 0),
        cache_creation_input_tokens=cache_write,
        cache_read_input_tokens=cache_read,
    )
    models = list((data.get("modelUsage") or {}).keys())
    parsed = data.get("structured_output")
    if structured and not isinstance(parsed, dict):
        # Older CLI versions put the JSON in `result`.
        try:
            parsed = json.loads(data.get("result") or "")
        except ValueError:
            parsed = None
        if not isinstance(parsed, dict):
            raise LLMError("claude -p ga ikke strukturert output")
    return AgentResponse(
        parsed=parsed if structured else None,
        text=data.get("result"),
        usage=usage,
        cost_usd=float(data.get("total_cost_usd") or 0.0),
        model=models[0] if models else fallback_model,
        duration_ms=int(data.get("duration_ms") or 0),
    )


class ClaudeCodeBackend:
    name = "claude_code"

    def __init__(self, cli: str | None = None, sandbox_dir: Path | None = None) -> None:
        self._cli = cli
        self._sandbox_dir = sandbox_dir

    def run(self, req: AgentRequest) -> AgentResponse:
        from jobsearcher.config import env, load_settings

        llm = load_settings().llm
        cli = self._cli or find_cli()
        sandbox = self._sandbox_dir or env().llm_sandbox_dir
        sandbox.mkdir(parents=True, exist_ok=True)
        timeout = req.timeout_s or llm.timeout_s
        if req.max_budget_usd is None:
            req = dataclasses.replace(req, max_budget_usd=llm.max_budget_usd_per_call)

        # The prompt file lives outside the sandbox so the working directory stays empty.
        fd, prompt_path = tempfile.mkstemp(prefix=f"js-{req.agent}-", suffix=".md")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(req.system_prompt)
            cmd = build_command(req, cli, Path(prompt_path))
            started = time.monotonic()
            try:
                proc = subprocess.run(
                    cmd,
                    input=req.full_user_content(),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=sandbox,
                    env=child_env(),
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired as e:
                raise LLMError(f"claude -p brukte mer enn {timeout} s") from e
            except OSError as e:
                raise LLMError(f"Kunne ikke starte claude -p: {e}") from e
            elapsed_ms = int((time.monotonic() - started) * 1000)
        finally:
            Path(prompt_path).unlink(missing_ok=True)

        try:
            data = json.loads(proc.stdout)
        except ValueError as e:
            tail = (proc.stderr or proc.stdout or "").strip()[-500:]
            raise LLMError(f"claude -p ga ugyldig svar (exit {proc.returncode}): {tail}") from e
        resp = parse_result(
            data, structured=req.output_schema is not None, fallback_model=MODEL_ALIASES[req.model_tier]
        )
        resp.duration_ms = resp.duration_ms or elapsed_ms
        log.info(
            "claude_code call",
            extra={
                "data": {
                    "agent": req.agent,
                    "model": resp.model,
                    "input_tokens": resp.usage.input_tokens,
                    "output_tokens": resp.usage.output_tokens,
                    "cost_usd": resp.cost_usd,
                    "wall_ms": elapsed_ms,
                }
            },
        )
        return resp
