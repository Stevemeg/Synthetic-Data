from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException

from ..core.errors import AppError
from ..core.logging import log_event
from ..schemas.platform import ErrorResponse

ERRORS = {
    400: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    413: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
    501: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


def error_response(request_id: str, code: str, message: str, status: int):
    return JSONResponse(
        {"error": {"code": code, "message": message, "request_id": request_id}},
        status_code=status,
        headers={
            "X-Request-ID": request_id,
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


def install_handlers(app: FastAPI):
    @app.exception_handler(AppError)
    async def domain_error(request: Request, error: AppError):
        code = "ENGINE_NOT_AVAILABLE" if error.code == "unavailable" else error.code.upper()
        log_event("request_rejected", error_code=code, status=error.status)
        return error_response(request.state.request_id, code, str(error), error.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error):
        return error_response(
            request.state.request_id,
            "REQUEST_VALIDATION_FAILED",
            "Request validation failed. Check IDs, fields, and bounds.",
            422,
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        message = (
            "Endpoint does not exist" if error.status_code == 404 else "HTTP request was rejected"
        )
        return error_response(
            request.state.request_id, f"HTTP_{error.status_code}", message, error.status_code
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error(request: Request, error):
        log_event("database_constraint_rejected", error_code="DATABASE_CONSTRAINT", status=409)
        return error_response(
            request.state.request_id,
            "DATABASE_CONSTRAINT",
            "Operation conflicts with a database invariant",
            409,
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error):
        log_event("database_unavailable", exception_type=type(error).__name__, status=503)
        return error_response(
            request.state.request_id,
            "DATABASE_UNAVAILABLE",
            "Database operation is unavailable",
            503,
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error):
        log_event(
            "request_failed",
            request_id=request.state.request_id,
            exception_type=type(error).__name__,
            status=500,
        )
        return error_response(
            request.state.request_id,
            "INTERNAL_ERROR",
            "Operation failed; use the request ID when checking server logs",
            500,
        )
