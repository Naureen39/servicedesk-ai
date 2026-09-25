"""Admin endpoints (Section 2.5): users, roles, KB listing, settings, audit log.

User/role management and audit-log reading are real against the identity tables this phase
owns. Knowledge base editing/publishing and persisted, editable runtime settings (provider
order, thresholds, daily budgets) are Section 8.3 Admin.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.permissions import (
    PERM_AUDIT_READ,
    PERM_KB_READ,
    PERM_KB_WRITE,
    PERM_ROLES_MANAGE,
    PERM_SETTINGS_MANAGE,
    PERM_USERS_MANAGE,
)
from app.core.security import hash_password
from app.db.base import get_db
from app.db.models.identity import AppSettings, AuditLog, Role, User
from app.db.models.knowledge import KbDocument
from app.schemas.admin import (
    AppSettingsOut,
    AppSettingsPatch,
    AuditLogOut,
    KbDocumentCreate,
    KbDocumentDetailOut,
    KbDocumentOut,
    KbDocumentUpdate,
    KbPublishResult,
    RoleOut,
    UserCreate,
    UserOut,
    UserPatch,
)
from app.services import kb_admin, settings_store
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


@router.get("/kb/{doc_id}", response_model=KbDocumentDetailOut)
async def get_kb_document(
    doc_id: int,
    _: CurrentUser = Depends(require_permission(PERM_KB_READ)),
    db: AsyncSession = Depends(get_db),
) -> KbDocumentDetailOut:
    result = await db.execute(select(KbDocument).where(KbDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise AppError(404, "Document not found", type_slug="https://meridian.example/problems/not-found")
    try:
        content = kb_admin.read_document(doc.source_path)
    except kb_admin.KbDocumentNotFoundError:
        content = ""
    return KbDocumentDetailOut(
        id=doc.id, source_path=doc.source_path, title=doc.title,
        document_hash=doc.document_hash, updated_at=doc.updated_at, content=content,
    )


@router.post("/kb", response_model=KbDocumentDetailOut, status_code=201)
async def create_kb_document(
    payload: KbDocumentCreate,
    user: CurrentUser = Depends(require_permission(PERM_KB_WRITE)),
    db: AsyncSession = Depends(get_db),
    ip: str = Depends(get_client_ip),
) -> KbDocumentDetailOut:
    """Section 8.3: "Markdown editor with preview, publish triggers re-embedding" -- writes the
    real markdown file and immediately publishes it (chunk + embed), so a new document is
    searchable right away rather than left in a half-created state until a separate publish
    call."""
    source_path = f"dataset/reference/knowledge_base/{payload.source_path.strip('/')}"
    if not source_path.endswith(".md"):
        source_path += ".md"
    try:
        kb_admin.read_document(source_path)
        raise AppError(409, "A document already exists at this path", type_slug="https://meridian.example/problems/conflict")
    except kb_admin.KbDocumentNotFoundError:
        pass

    kb_admin.write_document(source_path, payload.content)
    await kb_admin.republish_document(db, source_path, title=payload.title)

    result = await db.execute(select(KbDocument).where(KbDocument.source_path == source_path))
    doc = result.scalar_one()
    await record_audit(db, actor_user_id=user.id, action="kb.create", entity_type="kb_document", entity_id=str(doc.id), after={"source_path": source_path}, ip=ip)
    await db.commit()
    return KbDocumentDetailOut(id=doc.id, source_path=doc.source_path, title=doc.title, document_hash=doc.document_hash, updated_at=doc.updated_at, content=payload.content)


@router.put("/kb/{doc_id}", response_model=KbDocumentDetailOut)
async def update_kb_document(
    doc_id: int,
    payload: KbDocumentUpdate,
    user: CurrentUser = Depends(require_permission(PERM_KB_WRITE)),
    db: AsyncSession = Depends(get_db),
    ip: str = Depends(get_client_ip),
) -> KbDocumentDetailOut:
    """Saves the edit to disk but does NOT re-embed -- that's the separate `/publish` call
    below, matching the plan's "Markdown editor with preview, publish triggers re-embedding"
    (editing and publishing are deliberately different actions)."""
    result = await db.execute(select(KbDocument).where(KbDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise AppError(404, "Document not found", type_slug="https://meridian.example/problems/not-found")

    kb_admin.write_document(doc.source_path, payload.content)
    if payload.title:
        doc.title = payload.title
    await record_audit(db, actor_user_id=user.id, action="kb.update", entity_type="kb_document", entity_id=str(doc.id), ip=ip)
    await db.commit()
    return KbDocumentDetailOut(id=doc.id, source_path=doc.source_path, title=doc.title, document_hash=doc.document_hash, updated_at=doc.updated_at, content=payload.content)


@router.post("/kb/{doc_id}/publish", response_model=KbPublishResult)
async def publish_kb_document(
    doc_id: int,
    user: CurrentUser = Depends(require_permission(PERM_KB_WRITE)),
    db: AsyncSession = Depends(get_db),
    ip: str = Depends(get_client_ip),
) -> KbPublishResult:
    result = await db.execute(select(KbDocument).where(KbDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise AppError(404, "Document not found", type_slug="https://meridian.example/problems/not-found")

    outcome = await kb_admin.republish_document(db, doc.source_path, title=doc.title)
    await record_audit(db, actor_user_id=user.id, action="kb.publish", entity_type="kb_document", entity_id=str(doc_id), after=outcome, ip=ip)
    await db.commit()
    return KbPublishResult(**outcome)


@router.get("/settings", response_model=AppSettingsOut)
async def get_admin_settings(
    _: CurrentUser = Depends(require_permission(PERM_SETTINGS_MANAGE)), db: AsyncSession = Depends(get_db)
) -> AppSettings:
    result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
    return result.scalar_one()


@router.patch("/settings", response_model=AppSettingsOut)
async def patch_admin_settings(
    payload: AppSettingsPatch,
    user: CurrentUser = Depends(require_permission(PERM_SETTINGS_MANAGE)),
    db: AsyncSession = Depends(get_db),
    ip: str = Depends(get_client_ip),
) -> AppSettings:
    result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
    row = result.scalar_one()
    changes = payload.model_dump(exclude_unset=True)
    # audit_logs.before/after are JSON columns; the Numeric(4,3) threshold columns come back
    # as Decimal, which json.dumps chokes on, so cast to float for the audit trail.
    before = {k: float(v) if isinstance(v := getattr(row, k), Decimal) else v for k in changes}
    for field, value in changes.items():
        setattr(row, field, value)

    await record_audit(db, actor_user_id=user.id, action="settings.update", entity_type="app_settings", entity_id="1", before=before, after=changes, ip=ip)
    await db.commit()
    await settings_store.refresh(db)
    await db.refresh(row)
    return row


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
