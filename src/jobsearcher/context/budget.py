"""Token budget (ARCHITECTURE §6.2 "Budsjett").

Estimate: characters / 3.5. Over budget, parts with priority 3 are dropped first, then priority 2
(last added first). Priority 1 is never dropped; if it still does not fit, the call fails.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

CHARS_PER_TOKEN = 3.5


class BudgetExceeded(RuntimeError):
    pass


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def truncate(text: str, max_tokens: int) -> str:
    """Cut text to a token budget. Uses the cleaner's truncation when available."""
    try:
        from jobsearcher.pipeline.clean import truncate_for_budget
    except ImportError:
        truncate_for_budget = None
    if truncate_for_budget is not None:
        return truncate_for_budget(text, max_tokens)
    limit = int(max_tokens * CHARS_PER_TOKEN)
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # Prefer ending at a paragraph or sentence boundary in the last 20 %.
    for sep in ("\n\n", "\n", ". "):
        idx = cut.rfind(sep)
        if idx > limit * 0.8:
            cut = cut[: idx + len(sep)]
            break
    return cut.rstrip() + "\n[…]"


@dataclass
class Part:
    name: str
    text: str
    priority: int = 1
    shared: bool = True
    """Shared (cacheable) context vs per-call content."""

    @property
    def tokens(self) -> int:
        return estimate_tokens(self.text)


def fit(parts: list[Part], budget: int, fixed_tokens: int = 0) -> tuple[list[Part], list[str]]:
    """Drop priority 3, then 2 parts until the total fits. Returns (kept, dropped names)."""
    kept = list(parts)
    dropped: list[str] = []
    total = fixed_tokens + sum(p.tokens for p in kept)
    for prio in (3, 2):
        for part in reversed([p for p in kept if p.priority == prio]):
            if total <= budget:
                break
            kept.remove(part)
            dropped.append(part.name)
            total -= part.tokens
    if total > budget:
        raise BudgetExceeded(
            f"Konteksten er ~{total} tokens, over budsjettet på {budget}, selv etter kutt av prioritet 2–3."
        )
    return kept, dropped
