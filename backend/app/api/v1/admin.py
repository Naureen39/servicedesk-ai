"""Admin endpoints (Section 2.5): users, roles, KB listing, settings, audit log.

User/role management and audit-log reading are real against the identity tables this phase
owns. `/admin/kb` lists `kb_documents` (populated once the Phase 3 ingestion job runs).
`/admin/settings` is read-only here; persisted runtime settings (provider order, thresholds,
daily budgets) are wired to the LLM router configuration in Phase 4.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.permissions import (
    PERM_AUDIT_READ,
    PERM_KB_READ,
    PERM_ROLES_MANAGE,
    PERM_SETTINGS_MANAGE,
    PERM_USERS_MANAGE,
)
from app.core.security import hash_password
from app.db.base import get_db
from app.db.models.identity import AuditLog, Role, User
from app.db.models.knowledge import KbDocument
from app.schemas.admin import AuditLogOut, KbDocumentOut, RoleOut, UserCreate, UserOut, UserPatch
from app.services.audit import record_audit

from .deps import CurrentUser, get_client_ip, require_permission

router = APIRouter(prefix="/admin", tags=["admin"])
settings = get_settings()


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        mfa_enabled=user.mfa_enabled,
        location_id=user.location_id,
        roles=[r.name for r in user.roles],
    )


@router.get("/users", response_model=list[UserOut])
async def list_users(
    _: CurrentUser = Depends(require_permission(PERM_USERS_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> list[UserOut]:
    result = await db.execute(select(User).options(selectinload(User.roles)))
    return [_user_out(u) for u in result.scalars().all()]


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    payload: UserCreate,
    user: CurrentUser = Depends(require_permission(PERM_USERS_MANAGE)),
    db: AsyncSession = Depends(get_db),
    ip: str = Depends(get_client_ip),
) -> UserOut:
    existing = await db.execute(select(User).where(User.email == payload.email.lower()))
    if existing.scalar_one_or_none() is not None:
        raise AppError(409, "A user with this email already exists", type_slug="https://meridian.example/problems/conflict")

    roles: list[Role] = []
    if payload.role_names:
        role_result = await db.execute(select(Role).where(Role.name.in_(payload.role_names)))
        roles = list(role_result.scalars().all())
        found_names = {r.name for r in roles}
        missing = set(payload.role_names) - found_names
        if missing:
            raise AppError(400, f"Unknown role(s): {', '.join(sorted(missing))}", type_slug="https://meridian.example/problems/validation-error")

    new_user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        location_id=payload.location_id,
        roles=roles,
    )
    db.add(new_user)
    await db.flush()

    await record_audit(
        db,
        actor_user_id=user.id,
        action="user.create",
        entity_type="user",
        entity_id=str(new_user.id),
        after={"email": new_user.email, "roles": payload.role_names},
        ip=ip,
    )
    await db.commit()
    await db.refresh(new_user, attribute_names=["roles"])
    return _user_out(new_user)


@router.patch("/users/{user_id}", response_model=UserOut)
async def patch_user(
    user_id: str,
    payload: UserPatch,
    current_user: CurrentUser = Depends(require_permission(PERM_USERS_MANAGE)),
    db: AsyncSession = Depends(get_db),
    ip: str = Depends(get_client_ip),
) -> UserOut:
    try:
        uuid.UUID(user_id)
    except ValueError:
        raise AppError(404, "User not found", type_slug="https://meridian.example/problems/not-found") from None

    result = await db.execute(select(User).options(selectinload(User.roles)).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if target is None:
        raise AppError(404, "User not found", type_slug="https://meridian.example/problems/not-found")

    before = {"is_active": target.is_active, "location_id": target.location_id, "roles": [r.name for r in target.roles]}

    if payload.is_active is not None:
        target.is_active = payload.is_active
    if payload.location_id is not None:
        target.location_id = payload.location_id
    if payload.role_names is not None:
        role_result = await db.execute(select(Role).where(Role.name.in_(payload.role_names)))
        target.roles = list(role_result.scalars().all())

    await record_audit(
        db,
        actor_user_id=current_user.id,
        action="user.update",
        entity_type="user",
        entity_id=user_id,
        before=before,
        after=payload.model_dump(exclude_unset=True),
        ip=ip,
    )
    await db.commit()
    await db.refresh(target, attribute_names=["roles"])
    return _user_out(target)


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(
    _: CurrentUser = Depends(require_permission(PERM_ROLES_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> list[RoleOut]:
    result = await db.execute(select(Role).options(selectinload(Role.permissions)))
    return [
        RoleOut(id=r.id, name=r.name, description=r.description, permissions=[p.code for p in r.permissions])
        for r in result.scalars().all()
    ]


@router.get("/kb", response_model=list[KbDocumentOut])
async def list_kb_documents(
    _: CurrentUser = Depends(require_permission(PERM_KB_READ)),
    db: AsyncSession = Depends(get_db),
) -> list[KbDocument]:
    result = await db.execute(select(KbDocument).order_by(KbDocument.title))
    return list(result.scalars().all())


@router.get("/settings")
async def get_admin_settings(_: CurrentUser = Depends(require_permission(PERM_SETTINGS_MANAGE))) -> dict:
    return {
        "llm_primary": settings.llm_primary,
        "llm_daily_request_budget_groq": settings.llm_daily_request_budget_groq,
        "llm_daily_request_budget_gemini": settings.llm_daily_request_budget_gemini,
        "embedding_model": settings.embedding_model,
        "note": "Persisted, editable runtime settings (confidence/cache thresholds, provider order) ship with the Phase 4 LLM router.",
    }


@router.get("/audit-logs", response_model=list[AuditLogOut])
async def list_audit_logs(
    entity_type: str | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    _: CurrentUser = Depends(require_permission(PERM_AUDIT_READ)),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLogOut]:
    stmt = select(AuditLog)
    if entity_type is not None:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return [
        AuditLogOut(
            id=row.id,
            actor_user_id=str(row.actor_user_id) if row.actor_user_id else None,
            action=row.action,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            ip=row.ip,
            created_at=row.created_at,
        )
        for row in result.scalars().all()
    ]
