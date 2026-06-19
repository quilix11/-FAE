from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from domain.exceptions import (
    AuthenticationError,
    ConcurrencyError,
    DomainError,
    DuplicateEntityError,
    EntityNotFoundError,
)


def setup_exception_handlers(app: FastAPI) -> None:
    """Register domain exception handlers on the FastAPI application."""

    @app.exception_handler(AuthenticationError)
    async def authentication_error_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"detail": str(exc)},
            headers={"WWW-Authenticate": "Bearer"},
        )


    @app.exception_handler(EntityNotFoundError)
    async def entity_not_found_handler(request: Request, exc: EntityNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)},
        )

    @app.exception_handler(ConcurrencyError)
    async def concurrency_error_handler(request: Request, exc: ConcurrencyError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": str(exc)},
        )

    @app.exception_handler(DuplicateEntityError)
    async def duplicate_entity_handler(request: Request, exc: DuplicateEntityError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": str(exc)},
        )

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)},
        )
