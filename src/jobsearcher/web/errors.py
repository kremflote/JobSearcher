"""Error responses in the contract shape `{"detail": ..., "code": ...}`."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from jobsearcher.api.schemas import ErrorResponse


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, detail: str) -> None:
        self.status_code = status_code
        self.code = code
        self.detail = detail


def not_implemented() -> ApiError:
    """Routes that exist in the contract but have no backend yet."""
    return ApiError(501, "not_implemented", "Endepunktet er ikke implementert ennå.")


ERROR_RESPONSES: dict[int | str, dict] = {
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    501: {"model": ErrorResponse},
}


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _handle(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(detail=exc.detail, code=exc.code).model_dump(),
        )
