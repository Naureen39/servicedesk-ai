"""Chat endpoints (Section 2.5). Session issuance, input validation, and message handling
(NLU, dialog management, retrieval, LLM routing) are all real as of Phase 4.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.exceptions import AppError
from app.core.rate_limit import limiter
from app.core.security import create_anonymous_session_token
from app.db.base import get_db
from app.db.models.assistant import Conversation, Message
from app.schemas.auth import ChatSessionResponse
from app.schemas.chat import ChatFeedbackRequest, ChatMessageRequest
from app.services.channel.web_chat import WebChatAdapter
from app.services.dialog.manager import handle_turn
from app.services.llm.factory import get_router

from .deps import get_anonymous_session

router = APIRouter(prefix="/chat", tags=["chat"])
_adapter = WebChatAdapter()


@router.post("/session", response_model=ChatSessionResponse)
async def create_chat_session(channel: str = "chat", db: AsyncSession = Depends(get_db)) -> ChatSessionResponse:
    """`channel="voice"` is how the Phase 6 voice modal gets a session token bound to a
    voice-tagged conversation before opening `WS /voice/session` -- same anonymous-session
    token mechanism as chat (Section 5.1 item 2: "the anonymous session token")."""
    if channel not in ("chat", "voice"):
        raise AppError(400, "channel must be 'chat' or 'voice'", type_slug="https://meridian.example/problems/validation")
    conversation_id = f"CONV-{uuid.uuid4().hex[:10].upper()}"
    db.add(
        Conversation(
            conversation_id=conversation_id,
            channel=channel,
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
    db: AsyncSession = Depends(get_db),
) -> dict:
    if payload.conversation_id != session.get("conversation_id"):
        raise AppError(
            403,
            "Session token is not bound to this conversation",
            type_slug="https://meridian.example/problems/forbidden",
        )

    result = await db.execute(select(Conversation).where(Conversation.conversation_id == payload.conversation_id))
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise AppError(404, "Conversation not found", type_slug="https://meridian.example/problems/not-found")

    turn = await _adapter.receive(payload.text, payload.conversation_id)
    turn_result = await handle_turn(db, conversation, turn.text, get_router(), channel=turn.channel)
    text = await _adapter.send(_response_from(turn_result))

    return {
        "conversation_id": payload.conversation_id,
        "message_id": turn_result.message_id,
        "text": text,
        "escalated": not turn_result.contained,
    }


def _response_from(turn_result):
    from app.services.channel.base import Response

    return Response(text=turn_result.text, escalated=not turn_result.contained)


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
async def chat_feedback(payload: ChatFeedbackRequest, session: dict = Depends(get_anonymous_session), db: AsyncSession = Depends(get_db)) -> None:
    if payload.conversation_id != session.get("conversation_id"):
        raise AppError(
            403,
            "Session token is not bound to this conversation",
            type_slug="https://meridian.example/problems/forbidden",
        )
    result = await db.execute(
        select(Message).where(Message.message_id == payload.message_id, Message.conversation_id == payload.conversation_id)
    )
    message = result.scalar_one_or_none()
    if message is None:
        raise AppError(404, "Message not found", type_slug="https://meridian.example/problems/not-found")
    message.helpful = payload.helpful
    await db.commit()
