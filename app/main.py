from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import Base, engine
from app.config import settings
from app.logging_config import configure_logging
from app.migrations import migrate_legacy_tables
from app.middleware import RequestLoggingMiddleware
from app.routers.auth import router as auth_router
from app.routers.chat import router as chat_router
from app.routers.uploads import router as uploads_router


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings.validate_startup()
    migrate_legacy_tables()
    Base.metadata.create_all(bind=engine)
    logger.info("Application startup complete; manual data upload is enabled")
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(chat_router, prefix=settings.api_prefix)
app.include_router(uploads_router, prefix=settings.api_prefix)


@app.exception_handler(HTTPException)
async def http_error_handler(_: Request, exception: HTTPException) -> JSONResponse:
    if isinstance(exception.detail, dict):
        detail = str(exception.detail.get("detail", "Request failed"))
        code = str(exception.detail.get("code", "request_error"))
    else:
        detail = str(exception.detail)
        code = "request_error"
    return JSONResponse(
        status_code=exception.status_code,
        content={"detail": detail, "code": code},
        headers=exception.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exception: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": "Request validation failed", "code": "validation_error", "errors": exception.errors()},
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(_: Request, exception: Exception) -> JSONResponse:
    logger.error(
        "Unhandled request exception type=%s",
        type(exception).__name__,
        exc_info=(type(exception), exception, exception.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "The server could not complete this request", "code": "internal_error"},
    )


@app.get("/")
def root() -> dict[str, str]:
    return {"app": settings.app_name, "status": "ok", "docs": "/docs"}


@app.get("/health")
@app.get(f"{settings.api_prefix}/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}
