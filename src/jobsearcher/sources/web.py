"""Helpers for sources that read ordinary web pages and feeds (Teamtailor, page watcher).

- `WEB_HEADERS`: an honest User-Agent that names the tool (matches `ROBOTS_AGENT`). Header
  values must be ASCII.
- `parse_job_posting`: the `JobPosting` object from a page's JSON-LD (Finn, most ATS pages).
- `page_markdown`: a career page (or one part of it, by CSS selector) as Markdown with absolute
  links, for hashing and for the extractor agent.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import urljoin

from markdownify import markdownify
from selectolax.lexbor import LexborHTMLParser

from jobsearcher.pipeline.clean import _DROP_TAGS, _tidy

WEB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JobSearcher/1.0; private job search)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "nb-NO,nb;q=0.9,no;q=0.8,en;q=0.6",
}
FEED_HEADERS = {**WEB_HEADERS, "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.5"}

# The ad cleaner's drop list, but keeping <form>: ASP.NET sites wrap the whole page in one.
_PAGE_DROP_TAGS = tuple(t for t in _DROP_TAGS if t != "form")
_MD_LINK = re.compile(r"\]\(([^)\s]+)\)")


def parse_job_posting(html: str) -> dict[str, Any] | None:
    """Return the JobPosting object from the page's JSON-LD (Finn wraps it in
    {"script:ld+json": {...}}; others use a plain object, a list or `@graph`)."""
    tree = LexborHTMLParser(html)
    for node in tree.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(node.text() or "")
        except ValueError:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("script:ld+json"), dict):
                item = item["script:ld+json"]
            graph = item.get("@graph") if isinstance(item, dict) else None
            for obj in graph if isinstance(graph, list) else [item]:
                if isinstance(obj, dict) and _is_type(obj.get("@type"), "JobPosting"):
                    return obj
    return None


def _is_type(value: Any, wanted: str) -> bool:
    return value == wanted or (isinstance(value, list) and wanted in value)


def page_markdown(html: str, base_url: str, selector: str | None = None) -> str:
    """Main content of a page as Markdown. Links are kept and made absolute (the extractor
    needs them); images, scripts and page chrome (nav, header, footer) are dropped.

    `selector` picks the part of the page to watch; without it (or when it matches nothing)
    `<main>` is used, else `<body>`."""
    tree = LexborHTMLParser(html)
    for tag in _PAGE_DROP_TAGS:
        for node in tree.css(tag):
            node.decompose()
    nodes = tree.css(selector) if selector else []
    if not nodes:
        main = tree.css_first("main") or tree.body or tree.root
        nodes = [main] if main is not None else []
    parts = []
    for node in nodes:
        md = markdownify(node.html or "", heading_style="ATX", bullets="-", strip=["img"])
        parts.append(_MD_LINK.sub(lambda m: f"]({urljoin(base_url, m.group(1))})", md))
    return _tidy("\n\n".join(parts)) or ""


def content_hash(text: str) -> str:
    """Hash of page text with whitespace normalized, so reflowed markup is not a change."""
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()[:16]
