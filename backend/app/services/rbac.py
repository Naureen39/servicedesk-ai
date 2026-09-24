"""Loads a user's effective roles and permissions from the RBAC tables."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.identity import Role, User


async def load_roles_and_permissions(db: AsyncSession, user_id: uuid.UUID) -> tuple[list[str], list[str]]:
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .where(User.id == user_id)
    )
    user = result.scalar_one()
    roles = [r.name for r in user.roles]
    permissions = sorted({p.code for r in user.roles for p in r.permissions})
    return roles, permissions
