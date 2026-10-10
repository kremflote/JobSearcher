"""FastAPI app. All JSON routes live under /api (docs/FRONTEND.md §7)."""

from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute

from jobsearcher import __version__
from jobsearcher.api.schemas import HealthStatus
from jobsearcher.web import errors
from jobsearcher.web.routes import (
    applications,
    drafts,
    jobs,
    logs,
    overview,
    profile,
    settings,
    tasks,
)


def _operation_id(route: APIRoute) -> str:
    return route.name


def create_app() -> FastAPI:
    app = FastAPI(
        title="JobSearcher API",
        version=__version__,
        generate_unique_id_function=_operation_id,
        separate_input_output_schemas=False,
    )
    errors.install(app)

    api = APIRouter(prefix="/api", responses=errors.ERROR_RESPONSES)

    @api.get("/health", tags=["health"])
    def health() -> HealthStatus:
        return HealthStatus(status="ok", version=__version__)

    for module in (overview, jobs, applications, drafts, profile, settings, logs, tasks):
        api.include_router(module.router)
    app.include_router(api)
    return app


app = create_app()
