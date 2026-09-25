"""Assistant Test Console (Section 8.3): "chat input plus a debug panel (detected intent,
confidence, slots, retrieved chunks, provider, tokens, latency) for client demos." Runs the
real dialog pipeline (same `handle_turn` chat uses) against a real conversation tagged
`channel="staff_test"` so these runs never mix into customer-facing analytics, then separately
surfaces the intent classifier, slot extractor, and retriever's own outputs for the debug
panel -- cheap local calls, not LLM calls, so duplicating them alongside the real turn costs
nothing extra.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import PERM_TEST_CONSOLE_USE
from app.db.base import get_db
from app.db.models.assistant import Conversation
from app.schemas.test_console import RetrievedChunkOut, TestConsoleRequest, TestConsoleResponse
from app.services.dialog.manager import handle_turn
from app.services.llm.factory import get_router
from app.services.nlu.intent_classifier import IntentClassifierNotTrained, predict_intent
from app.services.retrieval import retrieve_kb_chunks

from .deps import CurrentUser, require_permission

router = APIRouter(prefix="/test-console", tags=["test-console"])


@router.post("/message", response_model=TestConsoleResponse)
async def test_console_message(
    payload: TestConsoleRequest,
    _: CurrentUser = Depends(require_permission(PERM_TEST_CONSOLE_USE)),
    db: AsyncSession = Depends(get_db),
) -> TestConsoleResponse:
    conversation_id = payload.conversation_id
    if conversation_id is None:
        conversation_id = f"CONV-TEST-{uuid.uuid4().hex[:8].upper()}"
        db.add(Conversation(conversation_id=conversation_id, channel="staff_test", started_at=datetime.now(UTC)))
        await db.flush()
        conversation = await db.get(Conversation, conversation_id)
    else:
        conversation = await db.get(Conversation, conversation_id)
        if conversation is None:
            db.add(Conversation(conversation_id=conversation_id, channel="staff_test", started_at=datetime.now(UTC)))
            await db.flush()
            conversation = await db.get(Conversation, conversation_id)

    try:
        intent, confidence = predict_intent(payload.text)
    except IntentClassifierNotTrained:
        intent, confidence = None, None

    chunks = await retrieve_kb_chunks(db, payload.text, hybrid=True)

    t0 = time.monotonic()
    result = await handle_turn(db, conversation, payload.text, get_router(), channel="staff_test")
    latency_ms = int((time.monotonic() - t0) * 1000)

    slots = (conversation.state or {}).get("slots", {})

    return TestConsoleResponse(
        conversation_id=conversation_id,
        reply_text=result.text,
        escalated=not result.contained,
        intent=intent,
        confidence=confidence,
        slots=slots,
        retrieved_chunks=[
            RetrievedChunkOut(title=c.title, section=c.section, content=c.content, similarity=c.similarity) for c in chunks
        ],
        provider=result.llm_provider,
        tokens_in=result.llm_tokens_in,
        tokens_out=result.llm_tokens_out,
        cache_hit=result.cache_hit,
        latency_ms=latency_ms,
    )

