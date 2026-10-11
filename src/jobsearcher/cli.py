"""Command line entry point (ARCHITECTURE §15)."""

from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8765,
    reload: bool = False,
    build: bool = typer.Option(True, help="Rebuild web/dist first if the frontend changed."),
) -> None:
    """Start the API server (and the dashboard)."""
    import uvicorn

    from jobsearcher.db.session import init_db
    from jobsearcher.logging import setup_logging
    from jobsearcher.web.build import ensure_built

    setup_logging()
    if build:
        ensure_built()
    init_db()
    uvicorn.run("jobsearcher.web.app:app", host=host, port=port, reload=reload)


@app.command("init-db")
def init_db_cmd() -> None:
    """Create or upgrade the database (Alembic)."""
    from jobsearcher.db.session import init_db

    init_db()
    typer.echo("Databasen er oppdatert.")


@app.command()
def run(
    no_score: bool = typer.Option(False, "--no-score", help="Skip the filter agent (no LLM)."),
    source: list[str] = typer.Option(None, "--source", help="Only these sources (finn_api, nav)."),
    force: bool = typer.Option(
        False, "--force", help="Ignore source cooldowns and weekly searches (Finn). Use sparingly."
    ),
) -> None:
    """Collect, normalize, dedupe, filter and (unless --no-score) score jobs once."""
    from jobsearcher.db.session import init_db
    from jobsearcher.logging import setup_logging
    from jobsearcher.pipeline.lock import RunLockedError
    from jobsearcher.pipeline.run import run_pipeline

    setup_logging()
    init_db()
    try:
        summary = run_pipeline(trigger="manual", score=not no_score, sources=source or None, force=force)
    except RunLockedError:
        typer.echo("En kjøring pågår allerede (data/run.lock).", err=True)
        raise typer.Exit(1)
    typer.echo(summary.model_dump_json(indent=2))


@app.command()
def distill(force: bool = typer.Option(False, help="Distill even if the profile hash is unchanged.")) -> None:
    """Distill the profile into context/derived (profile_short, profile_long, voice)."""
    from jobsearcher.agents.distiller import distill as do_distill
    from jobsearcher.db.session import init_db
    from jobsearcher.logging import setup_logging

    setup_logging()
    init_db()
    changed = do_distill(force=force)
    typer.echo("Profilen er destillert." if changed else "Profilen er uendret; ingenting å gjøre.")


@app.command()
def rescore(
    all_jobs: bool = typer.Option(
        False, "--all", help="Every active, scored job, regardless of age, status or what it was scored with."
    ),
) -> None:
    """Rescore jobs scored with an older profile or prompt (§5.5), or all scored jobs with --all."""
    from sqlmodel import select

    from jobsearcher.agents.filter import rescore as do_rescore
    from jobsearcher.db.models import Evaluation, Job
    from jobsearcher.db.session import init_db, session_scope
    from jobsearcher.logging import setup_logging
    from jobsearcher.pipeline.lock import RunLock, RunLockedError

    setup_logging()
    init_db()
    try:
        with RunLock(), session_scope() as session:
            job_ids = None
            if all_jobs:
                job_ids = list(session.exec(
                    select(Job.id).where(
                        Job.active == True,  # noqa: E712
                        Job.filtered_out == False,  # noqa: E712
                        Job.id.in_(select(Evaluation.job_id)),
                    )
                ).all())
            summary = do_rescore(session, job_ids)
    except RunLockedError:
        typer.echo("En kjøring pågår allerede (data/run.lock).", err=True)
        raise typer.Exit(1)
    typer.echo(summary.model_dump_json(indent=2))


@app.command()
def digest(
    send: bool = typer.Option(False, "--send", help="Send the digest now (otherwise only a preview file)."),
) -> None:
    """Preview (default) or send the e-mail digest (§11)."""
    from jobsearcher.config import env
    from jobsearcher.db.repo import effective_settings
    from jobsearcher.db.session import init_db, session_scope
    from jobsearcher.notify.digest import send_digest

    init_db()
    preview = env().data_dir / "exports" / "digest-preview.html"
    preview.parent.mkdir(parents=True, exist_ok=True)
    with session_scope() as session:
        result = send_digest(session, effective_settings(session), dry_run_to=None if send else preview)
    typer.echo(f"Digest: {result}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
