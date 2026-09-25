"""Voice endpoint (Section 2.5 / Phase 6): validates the anonymous session token (same
mechanism as chat, `POST /chat/session?channel=voice`), loads the voice-tagged conversation,
and hands the connection to VoiceSession for real STT -> dialog manager -> TTS streaming.
"""

from __future__ import annotations

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.security import decode_anonymous_session_token
from app.db.base import async_session_factory
from app.db.models.assistant import Conversation
from app.services.voice.session import VoiceSession

router = APIRouter(tags=["voice"])


@router.websocket("/voice/session")
async def voice_session(websocket: WebSocket) -> None:
    await websocket.accept()
    token = websocket.query_params.get("token")
    try:
        if not token:
            raise ValueError("missing token")
        claims = decode_anonymous_session_token(token)
    except (jwt.InvalidTokenError, ValueError):
        await websocket.close(code=4401, reason="invalid or missing voice session token")
        return

    conversation_id = claims["conversation_id"]
    async with async_session_factory() as db:
        result = await db.execute(select(Conversation).where(Conversation.conversation_id == conversation_id))
        conversation = result.scalar_one_or_none()
        if conversation is None:
            await websocket.close(code=4404, reason="conversation not found")
            return

        session = VoiceSession(websocket, db, conversation)
        try:
            await session.run()
        except WebSocketDisconnect:
            pass
        finally:
            await db.commit()
