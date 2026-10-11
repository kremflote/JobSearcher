"""Cover letter export to .docx with python-docx (ARCHITECTURE §10.2, FRONTEND §5.5).

The letter is markdown without an address or date block (the writer leaves it out); the export
adds the sender (name and contact details from `profile.yaml`), the employer and the date.
Supported markdown: paragraphs, line breaks, `#` headings, `-`/`*`/`1.` lists, `**bold**`,
`*italic*`.
"""

from __future__ import annotations

import io
import re
from datetime import date
from typing import Any

import yaml
from docx import Document
from docx.shared import Pt

MONTHS = {
    "no": ["januar", "februar", "mars", "april", "mai", "juni", "juli", "august",
           "september", "oktober", "november", "desember"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"],
}
CONTACT_KEYS = ("email", "e-post", "epost", "phone", "telefon", "mobil", "location", "address",
                "adresse", "bosted", "website", "github", "linkedin")
INLINE = re.compile(r"(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|_[^_\s][^_]*_)")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")


def format_date(d: date, language: str = "no") -> str:
    month = MONTHS.get(language, MONTHS["no"])[d.month - 1]
    return f"{d.day}. {month} {d.year}" if language != "en" else f"{d.day} {month} {d.year}"


def sender_from_profile(profile_yaml: str | None) -> list[str]:
    """Name and contact lines. Accepts the details at top level or under `contact`/`kontakt`."""
    if not profile_yaml:
        return []
    try:
        data: Any = yaml.safe_load(profile_yaml) or {}
    except yaml.YAMLError:
        return []
    if not isinstance(data, dict):
        return []
    nested = data.get("contact") or data.get("kontakt") or {}
    if not isinstance(nested, dict):
        nested = {}
    merged = {**{str(k).lower(): v for k, v in data.items()}, **{str(k).lower(): v for k, v in nested.items()}}
    lines = []
    name = merged.get("name") or merged.get("navn")
    if isinstance(name, str) and name.strip():
        lines.append(name.strip())
    for key in CONTACT_KEYS:
        value = merged.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            lines.append(str(value).strip())
    return lines


def _add_runs(paragraph, text: str) -> None:
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            paragraph.add_run(part[2:-2]).bold = True
        elif len(part) > 2 and part[0] == part[-1] and part[0] in "*_":
            paragraph.add_run(part[1:-1]).italic = True
        else:
            paragraph.add_run(part)


def _add_block(doc, lines: list[str]) -> None:
    first = lines[0]
    heading = re.match(r"^(#{1,3})\s+(.*)$", first)
    if heading and len(lines) == 1:
        p = doc.add_paragraph()
        run = p.add_run(heading.group(2).strip())
        run.bold = True
        run.font.size = Pt(13 if len(heading.group(1)) == 1 else 12)
        return
    if all(LIST_ITEM.match(line) for line in lines):
        ordered = bool(re.match(r"^\s*\d", first))
        for line in lines:
            m = LIST_ITEM.match(line)
            assert m is not None
            p = doc.add_paragraph(style="List Number" if ordered else "List Bullet")
            _add_runs(p, m.group(1))
        return
    p = doc.add_paragraph()
    for i, line in enumerate(lines):
        if i:
            p.add_run().add_break()
        _add_runs(p, line.rstrip())


def letter_docx(
    markdown: str,
    *,
    sender: list[str] | None = None,
    recipient: str | None = None,
    on: date | None = None,
    language: str = "no",
) -> bytes:
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    style.paragraph_format.space_after = Pt(8)

    if sender:
        p = doc.add_paragraph()
        for i, line in enumerate(sender):
            if i:
                p.add_run().add_break()
            run = p.add_run(line)
            run.bold = i == 0
    if recipient:
        doc.add_paragraph(recipient)
    if on:
        doc.add_paragraph(format_date(on, language))

    block: list[str] = []
    for line in markdown.replace("\r\n", "\n").split("\n"):
        if line.strip():
            block.append(line)
        elif block:
            _add_block(doc, block)
            block = []
    if block:
        _add_block(doc, block)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def filename(company: str | None, version: int) -> str:
    """`Søknad <bedrift> v<versjon>.docx`, safe on Windows and in Content-Disposition."""
    name = re.sub(r'[\\/:*?"<>|\r\n]+', " ", f"Søknad {company or ''} v{version}.docx")
    return re.sub(r"\s+", " ", name).strip()
