from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_login_attempts: dict[str, deque[float]] = defaultdict(deque)
_limiter_lock = threading.Lock()
LOGIN_ATTEMPTS_PER_MINUTE = 10


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def create_access_token(user: User) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {"sub": str(user.id), "role": user.role, "exp": expires},
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


def _check_login_limit(client_key: str) -> None:
    now = time.monotonic()
    with _limiter_lock:
        attempts = _login_attempts[client_key]
        while attempts and now - attempts[0] >= 60:
            attempts.popleft()
        if len(attempts) >= LOGIN_ATTEMPTS_PER_MINUTE:
            raise HTTPException(status_code=429, detail={"detail": "Too many login attempts", "code": "rate_limited"})
        attempts.append(now)


def get_current_user(
    request: Request,
    database: Annotated[Session, Depends(get_db)],
) -> User:
    token = request.cookies.get("gcc_access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"detail": "Authentication required", "code": "unauthorized"})
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        user_id = int(payload.get("sub", ""))
    except (JWTError, TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"detail": "Invalid or expired session", "code": "invalid_token"}) from None
    user = database.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"detail": "Invalid or expired session", "code": "invalid_token"})
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"detail": "Administrator access required", "code": "forbidden"})
    return user
