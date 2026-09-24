"""Voice endpoint (Section 2.5). The browser-based voice agent (STT/TTS/barge-in) is Phase 6;
this WebSocket validates the anonymous session token and then closes with a clear reason so
the endpoint is real and testable without pulling in Phase 6's audio pipeline.
"""

from __future__ import annotations

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import decode_anonymous_session_token

router = APIRouter(tags=["voice"])

NOT_IMPLEMENTED_CODE = 4501


@router.websocket("/voice/session")
async def voice_session(websocket: WebSocket) -> None:
    await websocket.accept()
    token = websocket.query_params.get("token")
    try:
        if not token:
            raise ValueError("missing token")
        decode_anonymous_session_token(token)
    except (jwt.InvalidTokenError, ValueError):
        await websocket.close(code=4401, reason="invalid or missing chat session token")
        return

    try:
        await websocket.send_json(
            {
                "type": "error",
                "detail": "Voice streaming (STT/TTS/barge-in) is implemented in Phase 6 (Voice Agent)",
            }
        )
        await websocket.close(code=NOT_IMPLEMENTED_CODE, reason="voice pipeline not implemented until Phase 6")
    except WebSocketDisconnect:
        return
