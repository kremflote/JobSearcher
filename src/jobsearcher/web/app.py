"""FastAPI app. All JSON routes live under /api (docs/FRONTEND.md §7).

If `web/dist/` exists, the built SPA is served at `/` with index.html as fallback for
client-side routes. /api routes are registered first and never fall through to the SPA.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse
from fastapi.routing import APIRoute

from jobsearcher import __version__
from jobsearcher.api.schemas import HealthStatus
from jobsearcher.config import ROOT
from jobsearcher.web import errors
from jobsearcher.web.errors import ApiError
from jobsearcher.web.routes import (
    applications,
    drafts,
    jobs,
    llm,
    logs,
    overview,
    profile,
    rescore,
    settings,
    tasks,
)

DIST = ROOT / "web" / "dist"


def _operation_id(route: APIRoute) -> str:
    return route.name


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    from jobsearcher.db.session import init_db
    from jobsearcher.web.tasks import start_runner, stop_runner

    from jobsearcher.scheduler import start_scheduler, stop_scheduler

    init_db()
    start_runner()
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()
        stop_runner()


def create_app(dist: Path | None = DIST) -> FastAPI:
    app = FastAPI(
        title="JobSearcher API",
        version=__version__,
        generate_unique_id_function=_operation_id,
        separate_input_output_schemas=False,
        lifespan=lifespan,
    )
    errors.install(app)

    api = APIRouter(prefix="/api", responses=errors.ERROR_RESPONSES)

    @api.get("/health", tags=["health"])
    def health() -> HealthStatus:
        return HealthStatus(status="ok", version=__version__)

    for module in (
        overview,
        llm,
        jobs,
        applications,
        drafts,
        profile,
        settings,
        rescore,
        logs,
        tasks,
    ):
        api.include_router(module.router)
    app.include_router(api)

    if dist is not None and (dist / "index.html").is_file():
        _mount_spa(app, dist)
    return app


def _mount_spa(app: FastAPI, dist: Path) -> None:
    root = dist.resolve()
    index = root / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise ApiError(404, "not_found", "Fant ikke endepunktet.")
        if path:
            candidate = (root / path).resolve()
            if candidate.is_relative_to(root) and candidate.is_file():
                return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


app = create_app()
