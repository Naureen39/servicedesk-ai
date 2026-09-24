"""Audit logging for mutating actions (Section 2.3: "Every mutating action writes to
audit_logs (actor, action, entity, before/after diff, IP, user agent)")."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.identity import AuditLog


async def record_audit(
    db: AsyncSession,
    *,
    actor_user_id: str | uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: str | None,
    before: dict | None = None,
    after: dict | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
            ip=ip,
            user_agent=user_agent,
        )
    )
