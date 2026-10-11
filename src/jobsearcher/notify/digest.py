"""Daily e-mail digest (ARCHITECTURE §11).

Sections, each left out when empty: deadlines in the next `notify.deadline_days` days for
Interessant/Utkast, new jobs since the last digest with score ≥ `thresholds.notify_min_score`
(per job type), follow-ups due today or earlier, and source health / cost warnings.
Nothing is sent when every section is empty. The time of the last digest is kept in
DATA_DIR/digest_state.json, so a job is announced once.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from html import escape
from pathlib import Path

from sqlmodel import Session, col, select

from jobsearcher.config import Settings, env, today
from jobsearcher.db.models import Application, Job

log = logging.getLogger(__name__)

STATE_FILE = "digest_state.json"
FIRST_DIGEST_LOOKBACK = timedelta(days=1)
CLOSED = ("ikke_aktuell", "avslag", "trukket", "utlopt")
TYPE_NAMES = {"permanent": "Fast", "trainee": "Trainee", "graduate": "Graduate", "summer": "Sommerjobb", "unknown": "Annet"}
STATUS_NAMES = {"interessant": "Interessant", "utkast": "Utkast", "sokt": "Søkt", "intervju": "Intervju", "tilbud": "Tilbud"}
WEEKDAYS = ("man.", "tir.", "ons.", "tor.", "fre.", "lør.", "søn.")


@dataclass
class DigestJob:
    id: int
    title: str
    company: str
    location: str | None
    job_type: str
    score: int | None
    deadline: date | None
    status: str | None = None


@dataclass
class FollowUp:
    application_id: int
    title: str
    company: str
    status: str
    what: str
    due: date


@dataclass
class Digest:
    deadlines: list[DigestJob] = field(default_factory=list)
    new_jobs: dict[str, list[DigestJob]] = field(default_factory=dict)
    follow_ups: list[FollowUp] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.deadlines or self.new_jobs or self.follow_ups or self.warnings)

    @property
    def new_count(self) -> int:
        return sum(len(v) for v in self.new_jobs.values())


# --- State ---------------------------------------------------------------------------------


def _state_path() -> Path:
    return env().data_dir / STATE_FILE


def last_sent_at() -> datetime | None:
    try:
        raw = json.loads(_state_path().read_text(encoding="utf-8")).get("last_sent_at")
        return datetime.fromisoformat(raw) if raw else None
    except (OSError, ValueError):
        return None


def mark_sent(at: datetime) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"last_sent_at": at.isoformat(timespec="seconds")}) + "\n", encoding="utf-8")


# --- Building ------------------------------------------------------------------------------


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def build_digest(
    session: Session,
    settings: Settings,
    *,
    since: datetime,
    source_warnings: list[str] | None = None,
    on: date | None = None,
) -> Digest:
    from jobsearcher.agents.filter import _latest_evaluations
    from jobsearcher.llm.costs import cost_status

    on = on or today()
    d = Digest(warnings=list(source_warnings or []))
    statuses = {a.job_id: a for a in session.exec(select(Application)).all()}

    # Deadlines for jobs the user has picked, soonest first.
    horizon = on + timedelta(days=settings.notify.deadline_days)
    picked = [a for a in statuses.values() if a.status in ("interessant", "utkast")]
    if picked:
        jobs = session.exec(
            select(Job).where(
                col(Job.id).in_([a.job_id for a in picked]),
                Job.deadline != None,  # noqa: E711
                col(Job.deadline) >= on,
                col(Job.deadline) <= horizon,
            )
        ).all()
        evs = _latest_evaluations(session, [j.id for j in jobs])
        d.deadlines = sorted(
            (_job(j, evs.get(j.id), statuses[j.id].status) for j in jobs), key=lambda j: (j.deadline, j.title)
        )

    # New, well-scored jobs not triaged yet.
    fresh = [
        j
        for j in session.exec(
            select(Job).where(Job.active == True, Job.filtered_out == False)  # noqa: E712
        ).all()
        if _aware(j.first_seen) >= since
        and (j.id not in statuses or statuses[j.id].status == "ny")
        and (j.deadline is None or j.deadline >= on)
    ]
    evs = _latest_evaluations(session, [j.id for j in fresh])
    threshold = settings.thresholds.notify_min_score
    for j in fresh:
        ev = evs.get(j.id)
        if ev is not None and ev.score >= threshold:
            d.new_jobs.setdefault(j.job_type, []).append(_job(j, ev))
    for jobs in d.new_jobs.values():
        jobs.sort(key=lambda j: -(j.score or 0))
    d.new_jobs = dict(sorted(d.new_jobs.items(), key=lambda kv: list(TYPE_NAMES).index(kv[0]) if kv[0] in TYPE_NAMES else 99))

    # Follow-ups and next steps due today or earlier, for open applications.
    open_apps = [a for a in statuses.values() if a.status not in CLOSED and a.status != "ny"]
    jobs_by_id = {j.id: j for j in session.exec(select(Job).where(col(Job.id).in_([a.job_id for a in open_apps]))).all()}
    for a in open_apps:
        job = jobs_by_id.get(a.job_id)
        if job is None:
            continue
        if a.next_step_at and a.next_step_at <= on:
            d.follow_ups.append(FollowUp(a.id, job.title, job.company, a.status, a.next_step or "Neste steg", a.next_step_at))
        if a.follow_up_at and a.follow_up_at <= on:
            d.follow_ups.append(FollowUp(a.id, job.title, job.company, a.status, "Følg opp søknaden", a.follow_up_at))
    d.follow_ups.sort(key=lambda f: (f.due, f.title))

    spent, cap, warn = cost_status(session)
    if warn:
        d.warnings.append(f"LLM-kostnaden denne måneden er ${spent:.2f} av taket på ${cap:.2f}.")
    return d


def _job(j: Job, ev, status: str | None = None) -> DigestJob:
    return DigestJob(j.id, j.title, j.company, j.location_text, j.job_type, ev.score if ev else None, j.deadline, status)


def source_warnings(summary) -> list[str]:
    """One line per source that failed or warned in this run (§12)."""
    out = []
    for s in getattr(summary, "sources", []) or []:
        if s.health in ("fail", "warn") and not s.skipped:
            what = "feilet" if s.health == "fail" else "ga en advarsel"
            detail = s.message or (s.errors[0] if s.errors else None)
            out.append(f"{s.source} {what}" + (f": {detail}" if detail else "."))
    return out


# --- Rendering -----------------------------------------------------------------------------


def subject(d: Digest, on: date | None = None) -> str:
    on = on or today()
    parts = []
    if d.deadlines:
        parts.append(f"{len(d.deadlines)} frist{'er' if len(d.deadlines) > 1 else ''}")
    if d.new_count:
        parts.append(f"{d.new_count} nye jobber")
    if d.follow_ups:
        parts.append(f"{len(d.follow_ups)} oppfølging{'er' if len(d.follow_ups) > 1 else ''}")
    if d.warnings:
        parts.append("varsel")
    return f"Jobbsøk {on.day}.{on.month}.: " + ", ".join(parts)


def _when(due: date, on: date) -> str:
    days = (due - on).days
    rel = "i dag" if days == 0 else "i morgen" if days == 1 else f"om {days} d" if days > 0 else f"{-days} d siden"
    return f"{WEEKDAYS[due.weekday()]} {due.day}.{due.month}. ({rel})"


def render_text(d: Digest, app_url: str, on: date | None = None) -> str:
    on = on or today()
    url = app_url.rstrip("/")
    lines: list[str] = []
    if d.deadlines:
        lines += ["FRISTER", *[f"- {j.title}, {j.company}: {_when(j.deadline, on)}  {url}/jobber/{j.id}" for j in d.deadlines], ""]
    if d.new_jobs:
        lines.append("NYE JOBBER")
        for t, jobs in d.new_jobs.items():
            lines.append(f"{TYPE_NAMES.get(t, t)}:")
            lines += [f"- [{j.score}] {j.title}, {j.company}{f' ({j.location})' if j.location else ''}  {url}/jobber/{j.id}" for j in jobs]
        lines.append("")
    if d.follow_ups:
        lines += ["OPPFØLGING", *[f"- {f.what}: {f.title}, {f.company} ({_when(f.due, on)})  {url}/tracker?app={f.application_id}" for f in d.follow_ups], ""]
    if d.warnings:
        lines += ["VARSLER", *[f"- {w}" for w in d.warnings], ""]
    lines.append(f"Åpne Jobbsøk: {url}/")
    return "\n".join(lines)


def render_html(d: Digest, app_url: str, on: date | None = None) -> str:
    on = on or today()
    url = escape(app_url.rstrip("/"), quote=True)
    muted = "color:#6b7280"
    parts = ['<div style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;font-size:14px;line-height:1.5;color:#111827;max-width:640px">']

    def h(title: str) -> None:
        parts.append(f'<h2 style="font-size:15px;margin:20px 0 6px">{escape(title)}</h2>')

    def link(path: str, text: str) -> str:
        return f'<a href="{url}{escape(path, quote=True)}" style="color:#2563eb;text-decoration:none">{escape(text)}</a>'

    if d.deadlines:
        h("Frister")
        parts.append("<ul style='padding-left:18px;margin:0'>")
        for j in d.deadlines:
            color = "#dc2626" if (j.deadline - on).days <= 1 else "#111827"
            parts.append(f"<li>{link(f'/jobber/{j.id}', j.title)} <span style='{muted}'>· {escape(j.company)}</span> "
                         f"<span style='color:{color}'>{escape(_when(j.deadline, on))}</span></li>")
        parts.append("</ul>")
    if d.new_jobs:
        h("Nye jobber")
        for t, jobs in d.new_jobs.items():
            parts.append(f"<div style='{muted};margin-top:6px'>{escape(TYPE_NAMES.get(t, t))}</div><ul style='padding-left:18px;margin:0'>")
            for j in jobs:
                where = f" · {escape(j.location)}" if j.location else ""
                parts.append(f"<li><b>{j.score}</b> {link(f'/jobber/{j.id}', j.title)} <span style='{muted}'>· {escape(j.company)}{where}</span></li>")
            parts.append("</ul>")
    if d.follow_ups:
        h("Oppfølging")
        parts.append("<ul style='padding-left:18px;margin:0'>")
        for f in d.follow_ups:
            parts.append(f"<li>{escape(f.what)}: {link(f'/tracker?app={f.application_id}', f.title)} "
                         f"<span style='{muted}'>· {escape(f.company)} · {escape(_when(f.due, on))}</span></li>")
        parts.append("</ul>")
    if d.warnings:
        h("Varsler")
        parts.append("<ul style='padding-left:18px;margin:0;color:#b45309'>")
        parts += [f"<li>{escape(w)}</li>" for w in d.warnings]
        parts.append("</ul>")
    parts.append(f"<p style='margin-top:24px'>{link('/', 'Åpne Jobbsøk')}</p></div>")
    return "\n".join(parts)


# --- Sending -------------------------------------------------------------------------------


def send_digest(session: Session, settings: Settings, *, summary=None, now: datetime | None = None, dry_run_to: Path | None = None) -> str:
    """Build and send the digest. Returns what happened (for logs and the CLI).

    `dry_run_to` writes the HTML there instead of sending and leaves the state untouched."""
    from jobsearcher.notify.email import EmailNotConfigured, send_email

    now = now or datetime.now(UTC)
    since = last_sent_at() or now - FIRST_DIGEST_LOOKBACK
    d = build_digest(session, settings, since=since, source_warnings=source_warnings(summary))
    if d.empty:
        return "ingenting å melde"
    html = render_html(d, settings.notify.app_url)
    if dry_run_to is not None:
        dry_run_to.write_text(html, encoding="utf-8")
        return f"skrevet til {dry_run_to}"
    try:
        send_email(subject(d), render_text(d, settings.notify.app_url), html)
    except EmailNotConfigured as e:
        return str(e)
    mark_sent(now)
    return "sendt"
