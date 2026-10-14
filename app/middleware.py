from __future__ import annotations

import logging
import time

from fastapi import Request, Response
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import settings


logger = logging.getLogger(__name__)


def _user_id(request: Request) -> int | None:
    token = request.cookies.get("gcc_access_token")
    if not token:
        return None
    try:
        return int(jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm]).get("sub", ""))
    except (JWTError, TypeError, ValueError):
        return None


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        excluded = path in {"/health", f"{settings.api_prefix}/health"}
        if excluded:
            return await call_next(request)

        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000)
            user_id = _user_id(request)
            logger.info(
                "inbound request method=%s path=%s status=%s duration_ms=%s user_id=%s",
                request.method,
                path,
                status_code,
                duration_ms,
                user_id,
            )
