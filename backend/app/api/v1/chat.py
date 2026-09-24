"""Chat endpoints (Section 2.5). Session issuance and input validation are real; the dialog
engine itself (intent classification, RAG, LLM routing) is Phase 4 and returns 501 here.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.exceptions import AppError
from app.core.rate_limit import limiter
from app.core.security import create_anonymous_session_token
from app.db.base import get_db
from app.db.models.assistant import Conversation
from app.schemas.auth import ChatSessionResponse
from app.schemas.chat import ChatFeedbackRequest, ChatMessageRequest

from .deps import get_anonymous_session

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/session", response_model=ChatSessionResponse)
async def create_chat_session(db: AsyncSession = Depends(get_db)) -> ChatSessionResponse:
    conversation_id = f"CONV-{uuid.uuid4().hex[:10].upper()}"
    db.add(
        Conversation(
            conversation_id=conversation_id,
            channel="chat",
            started_at=datetime.now(UTC),
            contained=False,
            escalated=False,
        )
    )
    await db.commit()

    token, expires_at = create_anonymous_session_token(conversation_id)
    ttl = int((expires_at - datetime.now(UTC)).total_seconds())
    return ChatSessionResponse(session_token=token, conversation_id=conversation_id, expires_in=max(ttl, 0))


@router.post("/message")
@limiter.limit("20/minute")
async def send_chat_message(
    request: Request,
    payload: ChatMessageRequest,
    session: dict = Depends(get_anonymous_session),
) -> dict:
    if payload.conversation_id != session.get("conversation_id"):
        raise AppError(
            403,
            "Session token is not bound to this conversation",
            type_slug="https://meridian.example/problems/forbidden",
        )
    # NLU, dialog management, retrieval, and the LLM router are implemented in Phase 4.
    raise AppError(
        501,
        "Chat message handling is implemented in Phase 4 (Conversational Engine)",
        type_slug="https://meridian.example/problems/not-implemented",
    )


@router.get("/stream/{conversation_id}")
async def stream_chat(conversation_id: str, session: dict = Depends(get_anonymous_session)) -> EventSourceResponse:
    if conversation_id != session.get("conversation_id"):
        raise AppError(
            403,
            "Session token is not bound to this conversation",
            type_slug="https://meridian.example/problems/forbidden",
        )

    async def _empty_stream():
        return
        yield  # pragma: no cover - makes this an async generator

    return EventSourceResponse(_empty_stream())


@router.post("/feedback", status_code=204)
async def chat_feedback(payload: ChatFeedbackRequest, session: dict = Depends(get_anonymous_session)) -> None:
    if payload.conversation_id != session.get("conversation_id"):
        raise AppError(
            403,
            "Session token is not bound to this conversation",
            type_slug="https://meridian.example/problems/forbidden",
        )
    # Persisting feedback onto the message row is wired up alongside the dialog engine (Phase 4).
