from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import _check_login_limit, create_access_token, get_current_user, hash_password, verify_password
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, SignupRequest, UserRead


router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        key="gcc_access_token",
        value=create_access_token(user),
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )


@router.post("/signup", response_model=UserRead, status_code=201)
def signup(
    payload: SignupRequest,
    response: Response,
    database: Annotated[Session, Depends(get_db)],
) -> UserRead:
    email = str(payload.email).lower()
    if database.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(
            status_code=409,
            detail={"detail": "An account with this email already exists", "code": "email_exists"},
        )
    role = "admin" if settings.admin_email and email == settings.admin_email.lower() else payload.role
    user = User(name=payload.name.strip(), email=email, password_hash=hash_password(payload.password), role=role)
    database.add(user)
    database.commit()
    database.refresh(user)
    _set_session_cookie(response, user)
    return UserRead.model_validate(user)


@router.post("/login", response_model=UserRead)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    database: Annotated[Session, Depends(get_db)],
) -> UserRead:
    client_key = request.client.host if request.client else "unknown"
    _check_login_limit(client_key)
    email = str(payload.email).lower()
    user = database.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail={"detail": "Incorrect email or password", "code": "invalid_credentials"},
        )
    _set_session_cookie(response, user)
    return UserRead.model_validate(user)


@router.post("/logout", status_code=204, response_class=Response, response_model=None)
def logout(response: Response) -> None:
    response.delete_cookie(
        "gcc_access_token",
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


@router.get("/me", response_model=UserRead)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> UserRead:
    return UserRead.model_validate(current_user)