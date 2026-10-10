"""Ad text cleaning (ARCHITECTURE §4.6).

- `html_to_markdown`: HTML (or plain text) → Markdown without scripts, navigation and share links.
- `shorten_boilerplate`: paragraphs the same employer repeats in many ads are shortened.
- `truncate_for_budget`: shortens text for an LLM slice; the stored text stays complete.
"""

from __future__ import annotations

import re

from markdownify import markdownify
from selectolax.lexbor import LexborHTMLParser

CHARS_PER_TOKEN = 3.5
CUT_MARKER = "[… teksten er forkortet …]"
GAP_MARKER = "[…]"
BOILERPLATE_MARKER = "[… fast tekst fra arbeidsgiveren, forkortet …]"

_DROP_TAGS = (
    "script", "style", "noscript", "nav", "header", "footer", "form", "button", "iframe",
    "svg", "template", "aside",
)
# Lines that are UI chrome on ad pages, not ad text.
_CHROME_LINES = re.compile(
    r"^\W*(del annonsen|del stillingen|del denne annonsen|del på \w+|tips en venn|rapporter annonsen"
    r"|skriv ut|lagre annonsen|share this job|share|print|tilbake til søk|søk her)\W*$",
    re.IGNORECASE,
)
_HTML_TAG = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>")

PRIORITY_KEYWORDS = (
    "kvalifikasjon", "krav", "arbeidsoppgave", "vi tilbyr", "søknad", "qualification",
    "requirement", "responsibilit", "what we offer", "we offer", "about you", "om deg",
    "ansvar", "erfaring", "experience", "frist", "deadline",
)


def html_to_markdown(html: str | None) -> str | None:
    """Convert ad HTML (or plain text) to tidy Markdown. None/empty → None."""
    if not html or not html.strip():
        return None
    if _HTML_TAG.search(html):
        tree = LexborHTMLParser(html)
        for tag in _DROP_TAGS:
            for node in tree.css(tag):
                node.decompose()
        root = tree.body or tree.root
        body_html = root.html if root is not None else html
        md = markdownify(body_html or "", heading_style="ATX", bullets="-", strip=["img", "a"])
    else:
        md = html
    return _tidy(md)


def _tidy(md: str) -> str | None:
    lines: list[str] = []
    for line in md.replace("\r\n", "\n").replace("\xa0", " ").split("\n"):
        line = line.rstrip()
        if _CHROME_LINES.match(line.strip()):
            continue
        lines.append(line)
    text = "\n".join(lines)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text or None


def split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _para_key(p: str) -> str:
    return re.sub(r"\s+", " ", p).strip().lower()


def shorten_boilerplate(text: str, other_texts: list[str], min_ads: int, min_chars: int = 120) -> str:
    """Shorten long paragraphs that occur in at least `min_ads` ads (this one included)
    from the same employer. Keeps the first sentence and adds a marker."""
    if not other_texts or min_ads <= 1:
        return text
    counts: dict[str, int] = {}
    for other in other_texts:
        for key in {_para_key(p) for p in split_paragraphs(other)}:
            counts[key] = counts.get(key, 0) + 1
    out: list[str] = []
    for p in split_paragraphs(text):
        if len(p) >= min_chars and counts.get(_para_key(p), 0) + 1 >= min_ads:
            first = re.split(r"(?<=[.!?])\s", p, maxsplit=1)[0]
            if len(first) > 200:
                first = first[:200].rstrip() + "…"
            out.append(f"{first} {BOILERPLATE_MARKER}")
        else:
            out.append(p)
    return "\n\n".join(out)


def estimate_tokens(text: str) -> int:
    return int(len(text) / CHARS_PER_TOKEN) + 1


def _is_heading(p: str) -> bool:
    s = p.strip()
    return s.startswith("#") or (len(s) <= 80 and "\n" not in s and (s.startswith("**") or s.endswith(":")))


def _has_keyword(p: str) -> bool:
    low = p.lower()
    return any(k in low for k in PRIORITY_KEYWORDS)


def truncate_for_budget(text: str | None, max_tokens: int) -> str:
    """Fit `text` into roughly `max_tokens` (tokens ≈ chars / 3.5).

    Keeps the intro (first two paragraphs), then paragraphs with priority keywords (and the
    paragraph right after a keyword heading), then the rest in order while there is room.
    Selected paragraphs keep their original order; gaps get `[…]`, and a cut marker is added.
    """
    if not text:
        return ""
    budget = int(max_tokens * CHARS_PER_TOKEN)
    if len(text) <= budget:
        return text
    paras = split_paragraphs(text)
    priority: list[int] = []
    for i, p in enumerate(paras):
        if i < 2:
            continue
        if _has_keyword(p) or (i > 0 and _is_heading(paras[i - 1]) and _has_keyword(paras[i - 1])):
            priority.append(i)
    order = [i for i in range(min(2, len(paras)))] + priority
    order += [i for i in range(len(paras)) if i not in set(order)]

    room = budget - len(CUT_MARKER) - 2
    chosen: dict[int, str] = {}
    for i in order:
        p = paras[i]
        cost = len(p) + len(GAP_MARKER) + 4
        if cost <= room:
            chosen[i] = p
            room -= cost
        elif room > 200:  # fill the remaining room with the start of this paragraph
            chosen[i] = p[: room - len(GAP_MARKER) - 6].rstrip() + " …"
            room = 0
        if room <= 0:
            break

    out: list[str] = []
    prev = -1
    for i in sorted(chosen):
        if i != prev + 1 and out:
            out.append(GAP_MARKER)
        out.append(chosen[i])
        prev = i
    out.append(CUT_MARKER)
    return "\n\n".join(out)
