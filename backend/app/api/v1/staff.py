"""Staff endpoints (Section 2.5): conversations, escalations, and the live portal feed.

Conversation/escalation listing and escalation status updates are real, RBAC- and
location-scoped queries and mutations against the Phase 1 data. The live WebSocket feed and
delivering a reply into an active customer session are wired up once the dialog engine and
channel adapters exist (Phase 4/6); `POST /escalations/{id}/reply` here records the reply and
audit trail for real, which is the part Phase 2 owns.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.permissions import (
    PERM_CONVERSATIONS_READ,
    PERM_ESCALATIONS_READ,
    PERM_ESCALATIONS_WRITE,
)
from app.db.base import get_db
from app.db.models.assistant import Conversation, Escalation, Message
from app.schemas.staff import (
    ConversationOut,
    EscalationOut,
    EscalationPatch,
    EscalationReplyRequest,
    MessageOut,
)
from app.services.audit import record_audit

from .deps import CurrentUser, get_client_ip, location_filter, require_permission

router = APIRouter(tags=["staff"])


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    location_id: int | None = Query(default=None),
    channel: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_permission(PERM_CONVERSATIONS_READ)),
    db: AsyncSession = Depends(get_db),
) -> list[Conversation]:
    scoped_location_id = location_filter(user, location_id)
    stmt = select(Conversation)
    if scoped_location_id is not None:
        stmt = stmt.where(Conversation.location_id == scoped_location_id)
    if channel is not None:
        stmt = stmt.where(Conversation.channel == channel)
    stmt = stmt.order_by(Conversation.started_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user: CurrentUser = Depends(require_permission(PERM_CONVERSATIONS_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Conversation).where(Conversation.conversation_id == conversation_id))
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise AppError(404, "Conversation not found", type_slug="https://meridian.example/problems/not-found")

    scoped_location_id = location_filter(user, conversation.location_id)
    if scoped_location_id is not None and conversation.location_id != scoped_location_id:
        raise AppError(403, "Conversation is outside your assigned location", type_slug="https://meridian.example/problems/forbidden")

    messages_result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.turn)
    )
    messages = list(messages_result.scalars().all())
    return {
        "conversation": ConversationOut.model_validate(conversation),
        "messages": [MessageOut.model_validate(m) for m in messages],
    }


@router.websocket("/portal/live")
async def portal_live(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json(
        {"type": "info", "detail": "Live conversation streaming is wired up alongside the Phase 4 dialog engine"}
    )
    await websocket.close(code=4501, reason="live feed not implemented until Phase 4/6")


@router.get("/escalations", response_model=list[EscalationOut])
async def list_escalations(
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    location_id: int | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_permission(PERM_ESCALATIONS_READ)),
    db: AsyncSession = Depends(get_db),
) -> list[Escalation]:
    scoped_location_id = location_filter(user, location_id)
    stmt = select(Escalation).join(Conversation, Escalation.conversation_id == Conversation.conversation_id)
    if scoped_location_id is not None:
        stmt = stmt.where(Conversation.location_id == scoped_location_id)
    if status is not None:
        stmt = stmt.where(Escalation.status == status)
    if priority is not None:
        stmt = stmt.where(Escalation.priority == priority)
    stmt = stmt.order_by(Escalation.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _load_scoped_escalation(db: AsyncSession, user: CurrentUser, escalation_id: str) -> Escalation:
    result = await db.execute(
        select(Escalation, Conversation.location_id)
        .join(Conversation, Escalation.conversation_id == Conversation.conversation_id)
        .where(Escalation.escalation_id == escalation_id)
    )
    row = result.first()
    if row is None:
        raise AppError(404, "Escalation not found", type_slug="https://meridian.example/problems/not-found")
    escalation, conv_location_id = row

    scoped_location_id = location_filter(user, conv_location_id)
    if scoped_location_id is not None and conv_location_id != scoped_location_id:
        raise AppError(403, "Escalation is outside your assigned location", type_slug="https://meridian.example/problems/forbidden")
    return escalation


@router.patch("/escalations/{escalation_id}", response_model=EscalationOut)
async def patch_escalation(
    escalation_id: str,
    payload: EscalationPatch,
    user: CurrentUser = Depends(require_permission(PERM_ESCALATIONS_WRITE)),
    db: AsyncSession = Depends(get_db),
    ip: str = Depends(get_client_ip),
) -> Escalation:
    escalation = await _load_scoped_escalation(db, user, escalation_id)

    before = {"status": escalation.status, "assigned_to": escalation.assigned_to}
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(escalation, field, value)
    if changes.get("status") == "resolved" and escalation.resolved_at is None:
        escalation.resolved_at = datetime.now(UTC)

    await record_audit(
        db,
        actor_user_id=user.id,
        action="escalation.update",
        entity_type="escalation",
        entity_id=escalation_id,
        before=before,
        after=changes,
        ip=ip,
    )
    await db.commit()
    await db.refresh(escalation)
    return escalation


@router.post("/escalations/{escalation_id}/reply", status_code=201)
async def reply_to_escalation(
    escalation_id: str,
    payload: EscalationReplyRequest,
    user: CurrentUser = Depends(require_permission(PERM_ESCALATIONS_WRITE)),
    db: AsyncSession = Depends(get_db),
    ip: str = Depends(get_client_ip),
) -> dict:
    escalation = await _load_scoped_escalation(db, user, escalation_id)

    count_result = await db.execute(
        select(Message).where(Message.conversation_id == escalation.conversation_id)
    )
    next_turn = len(list(count_result.scalars().all()))
    reply_id = f"MSG-{escalation_id}-{next_turn:03d}"
    db.add(
        Message(
            message_id=reply_id,
            conversation_id=escalation.conversation_id,
            turn=next_turn,
            sender="advisor",
            text=payload.text,
            created_at=datetime.now(UTC),
        )
    )
    await record_audit(
        db,
        actor_user_id=user.id,
        action="escalation.reply",
        entity_type="escalation",
        entity_id=escalation_id,
        after={"message_id": reply_id},
        ip=ip,
    )
    await db.commit()
    # Delivering this into the customer's live session happens via the channel adapter
    # (Phase 4 chat, Phase 6 voice); this record is what those phases will pick up and push.
    return {"message_id": reply_id, "delivered": False}
