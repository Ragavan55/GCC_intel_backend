from __future__ import annotations

import json
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import ai_answer
from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import ChatMessage, ChatSession, User


router = APIRouter(prefix="/chat", tags=["chat"])
_chat_attempts: dict[int, deque[float]] = defaultdict(deque)
_rate_lock = threading.Lock()


class ChatRequest(BaseModel):
    session_id: int | None = None
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    session_id: int
    reply: str
    sources: list[dict[str, str]]


def _check_rate_limit(user_id: int) -> None:
    now = time.monotonic()
    with _rate_lock:
        attempts = _chat_attempts[user_id]
        while attempts and now - attempts[0] >= 60:
            attempts.popleft()
        if len(attempts) >= settings.chat_rate_limit_per_minute:
            raise HTTPException(status_code=429, detail={"detail": "Chat limit reached. Wait a minute and try again.", "code": "chat_rate_limited"})
        attempts.append(now)


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    database: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ChatResponse:
    _check_rate_limit(user.id)
    session = database.get(ChatSession, payload.session_id) if payload.session_id else None
    if session is not None and session.user_id != user.id:
        raise HTTPException(status_code=404, detail={"detail": "Chat session not found", "code": "not_found"})
    if session is None:
        session = ChatSession(user_id=user.id)
        database.add(session)
        database.flush()
    question = payload.message.strip()
    prior_messages = list(
        database.scalars(
            select(ChatMessage).where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at.desc()).limit(8)
        )
    )
    history = [{"role": item.role, "content": item.content} for item in reversed(prior_messages) if item.role in {"user", "assistant"}]
    database.add(ChatMessage(session_id=session.id, role="user", content=question))
    database.flush()
    reply, sources = ai_answer(database, question, history)
    database.add(
        ChatMessage(
            session_id=session.id,
            role="assistant",
            content=reply,
            tool_calls_json=json.dumps(sources, ensure_ascii=True),
            source="database retrieval",
            confidence="Medium" if sources else "Low",
            last_verified_at=datetime.now(timezone.utc),
        )
    )
    database.commit()
    return ChatResponse(session_id=session.id, reply=reply, sources=sources)
