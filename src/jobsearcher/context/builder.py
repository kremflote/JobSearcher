"""Context builder: turns an agent's manifest (config/agents.yaml, ARCHITECTURE §6.2) into the
shared context and per-call content of one LLM request.

Format:
- every shared slice is wrapped as `<slice_name>…</slice_name>`
- every item (job) is wrapped as `<job_ad id="…" prefiltered="true|false">` with one section per
  per-item slice (`<meta>`, `<text>`). Ad text is untrusted data (§6.5) and is escaped so it
  cannot close the wrapper.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from jobsearcher.context import slices
from jobsearcher.context.budget import Part, estimate_tokens, fit

ITEM_SECTION_TAGS = {"job_ad": "text", "job_meta": "meta"}


class SliceSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    slice: str
    priority: int = 1
    max_tokens: int | None = None


class AgentManifest(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    model_tier: str = "fast"
    effort: str | None = None
    prompt: str
    batch_size: int = 1
    context: list[SliceSpec] = Field(default_factory=list)
    per_item: list[SliceSpec] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    input_budget_tokens: int = 30000
    output_schema: str


def load_manifest(name: str) -> AgentManifest:
    from jobsearcher.config import load_agents

    agents = load_agents()
    if name not in agents:
        raise KeyError(f"Agent {name!r} mangler i config/agents.yaml")
    return AgentManifest.model_validate({"name": name, **agents[name]})


@dataclass
class BuiltContext:
    shared: str
    items: str
    est_tokens: int
    dropped: list[str] = field(default_factory=list)


def _render_item(job: Any, specs: list[SliceSpec], ctx: slices.SliceContext) -> tuple[str, int]:
    item_ctx = slices.SliceContext(settings=ctx.settings, session=ctx.session, job=job, extras=ctx.extras)
    sections = []
    for spec in specs:
        text = slices.render(spec.slice, item_ctx, spec.model_dump())
        if text is None:
            continue
        tag = ITEM_SECTION_TAGS.get(spec.slice, spec.slice)
        sections.append(f"<{tag}>\n{text}\n</{tag}>")
    # An item block is kept or dropped as a whole; its most important slice decides.
    prio = min((s.priority for s in specs), default=1)
    prefiltered = "true" if getattr(job, "prefiltered", False) else "false"
    body = "\n".join(sections)
    return f'<job_ad id="{job.id}" prefiltered="{prefiltered}">\n{body}\n</job_ad>', prio


def build_context(
    manifest: AgentManifest,
    *,
    settings: Any,
    session: Any = None,
    items: list[Any] | None = None,
    extras: dict[str, Any] | None = None,
    system_prompt: str = "",
) -> BuiltContext:
    """Render shared slices and per-item blocks, applying the token budget."""
    extras = extras or {}
    ctx = slices.SliceContext(settings=settings, session=session, job=extras.get("job"), extras=extras)
    parts: list[Part] = []
    for spec in manifest.context:
        text = slices.render(spec.slice, ctx, spec.model_dump())
        if text:
            parts.append(Part(spec.slice, f"<{spec.slice}>\n{text}\n</{spec.slice}>", spec.priority, shared=True))
    for job in items or []:
        text, prio = _render_item(job, manifest.per_item, ctx)
        parts.append(Part(f"job_ad:{job.id}", text, prio, shared=False))

    kept, dropped = fit(parts, manifest.input_budget_tokens, fixed_tokens=estimate_tokens(system_prompt))
    shared = "\n\n".join(p.text for p in kept if p.shared)
    item_text = "\n\n".join(p.text for p in kept if not p.shared)
    est = estimate_tokens(system_prompt) + sum(p.tokens for p in kept)
    return BuiltContext(shared=shared, items=item_text, est_tokens=est, dropped=dropped)
