"""Running one agent call (ARCHITECTURE §6.3, §7.2).

`run_agent` builds the context from the agent's manifest, calls the backend, validates the
output against the Pydantic schema, retries once with the validation error in the prompt, and
records one `agent_runs` row (tokens, cost and duration summed over both attempts).
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlmodel import Session

from jobsearcher.agents.schemas import SCHEMAS
from jobsearcher.context.builder import AgentManifest, BuiltContext, build_context, load_manifest
from jobsearcher.context.loader import load_prompt
from jobsearcher.db.models import AgentRun
from jobsearcher.llm.base import AgentRequest, LLMBackend, LLMError, Usage, get_backend

log = logging.getLogger(__name__)


@dataclass
class AgentOutcome:
    output: BaseModel | None
    error: str | None
    model: str
    prompt_version: str
    cost_usd: float
    run_id: int | None
    context: BuiltContext | None = None

    @property
    def ok(self) -> bool:
        return self.output is not None and self.error is None


def _retry_message(error: str) -> str:
    return (
        "\n\nDitt forrige svar var ugyldig:\n"
        f"{error[:2000]}\n"
        "Svar på nytt med gyldig output etter skjemaet, for alle elementene."
    )


def run_agent(
    name: str,
    *,
    session: Session | None = None,
    items: list[Any] | None = None,
    extras: dict[str, Any] | None = None,
    instructions: str = "",
    backend: LLMBackend | None = None,
    job_ids: list[int] | None = None,
    application_id: int | None = None,
    check: Callable[[BaseModel], str | None] | None = None,
    manifest: AgentManifest | None = None,
) -> AgentOutcome:
    """Run agent `name` once (plus one retry on invalid output).

    `check` is an optional semantic validation; a non-None return triggers the retry like a
    schema error does. After the retry, a schema-valid output is returned even if `check` still
    complains (the error is reported in `AgentOutcome.error`).
    Context errors (missing derived profile, budget exceeded) are raised, not recorded.
    """
    from jobsearcher.llm.costs import effective_settings

    manifest = manifest or load_manifest(name)
    prompt = load_prompt(manifest.prompt)
    schema = SCHEMAS[manifest.output_schema]
    settings = effective_settings(session) if session is not None else _default_settings()
    backend = backend or get_backend(settings.llm.backend)

    built = build_context(
        manifest, settings=settings, session=session, items=items, extras=extras, system_prompt=prompt.body
    )
    user_content = "\n\n".join(x for x in (built.items, instructions) if x)
    req = AgentRequest(
        agent=name,
        system_prompt=prompt.body,
        shared_context=built.shared,
        user_content=user_content,
        model_tier=manifest.model_tier,  # type: ignore[arg-type]
        effort=manifest.effort,
        output_schema=schema,
        tools=list(manifest.tools),
        max_budget_usd=settings.llm.max_budget_usd_per_call,
        timeout_s=settings.llm.timeout_s,
    )

    usage = Usage()
    cost = 0.0
    duration = 0
    model = manifest.model_tier
    output: BaseModel | None = None
    error: str | None = None
    for attempt in range(2):
        try:
            resp = backend.run(req)
        except LLMError as e:
            error = str(e)
            output = None
            break
        usage = usage + resp.usage
        cost += resp.cost_usd
        duration += resp.duration_ms
        model = resp.model
        try:
            output = schema.model_validate(resp.parsed if resp.parsed is not None else {})
            error = check(output) if check else None
        except ValidationError as e:
            output, error = None, f"Valideringsfeil: {e}"
        if error is None or attempt == 1:
            break
        log.warning("agent output invalid, retrying", extra={"data": {"agent": name, "error": error[:500]}})
        req = dataclasses.replace(req, user_content=user_content + _retry_message(error))

    run = AgentRun(
        agent=name,
        job_ids=list(job_ids or []),
        application_id=application_id,
        backend=getattr(backend, "name", type(backend).__name__),
        model=model,
        prompt_version=prompt.version,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=round(cost, 6),
        duration_ms=duration,
        status="ok" if output is not None and error is None else "error",
        error=error,
    )
    run_id = _record(run, session)
    return AgentOutcome(
        output=output,
        error=error,
        model=model,
        prompt_version=prompt.version,
        cost_usd=cost,
        run_id=run_id,
        context=built,
    )


def _default_settings():
    from jobsearcher.db.session import session_scope
    from jobsearcher.llm.costs import effective_settings

    try:
        with session_scope() as s:
            return effective_settings(s)
    except Exception:  # DB not initialised yet: plain settings.yaml
        from jobsearcher.config import load_settings

        return load_settings()


def _record(run: AgentRun, session: Session | None) -> int | None:
    if session is not None:
        session.add(run)
        session.flush()
        return run.id
    from jobsearcher.db.session import session_scope

    with session_scope() as s:
        s.add(run)
        s.flush()
        return run.id
