"""Seeds permissions, roles, the role -> permission matrix, and one demo account per role
(Makefile `seed` target). Idempotent: safe to re-run against an already-seeded database.

Demo credentials (documented here and in the README once written):
  admin@meridianauto.example / MeridianDemo!Admin1   (MFA required; see printed TOTP secret)
  manager@meridianauto.example / MeridianDemo!Mgr1
  advisor@meridianauto.example / MeridianDemo!Adv1    (scoped to Riverside, location_id=1)
  analyst@meridianauto.example / MeridianDemo!Analyst1
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.permissions import ALL_PERMISSIONS, ALL_ROLES, ROLE_PERMISSIONS
from app.core.security import generate_totp_secret, hash_password
from app.db.base import async_session_factory
from app.db.models.identity import MfaSecret, Permission, Role, User

ROLE_DESCRIPTIONS = {
    "admin": "Everything: user and role management, system settings, audit log",
    "service_manager": "All dashboards, escalations, appointments, knowledge base edit, assistant settings",
    "service_advisor": "Live conversations, escalations assigned to them, appointments, test console",
    "analyst": "Read-only analytics and exports",
}

DEMO_USERS = [
    {"email": "admin@meridianauto.example", "password": "MeridianDemo!Admin1", "role": "admin", "mfa": True, "location_id": None, "display_name": "Ada Ramirez"},
    {"email": "manager@meridianauto.example", "password": "MeridianDemo!Mgr1", "role": "service_manager", "mfa": False, "location_id": None, "display_name": "Devon Marsh"},
    {"email": "advisor@meridianauto.example", "password": "MeridianDemo!Adv1", "role": "service_advisor", "mfa": False, "location_id": 1, "display_name": "Priya Natarajan"},
    {"email": "analyst@meridianauto.example", "password": "MeridianDemo!Analyst1", "role": "analyst", "mfa": False, "location_id": None, "display_name": "Yusuf Rahman"},
]


async def seed_permissions(db: AsyncSession) -> dict[str, Permission]:
    result = await db.execute(select(Permission))
    existing = {p.code: p for p in result.scalars().all()}
    for code in ALL_PERMISSIONS:
        if code not in existing:
            perm = Permission(code=code)
            db.add(perm)
            existing[code] = perm
    await db.flush()
    return existing


async def seed_roles(db: AsyncSession, permissions: dict[str, Permission]) -> dict[str, Role]:
    result = await db.execute(select(Role).options(selectinload(Role.permissions)))
    existing = {r.name: r for r in result.scalars().all()}
    for name in ALL_ROLES:
        role = existing.get(name)
        if role is None:
            role = Role(name=name, description=ROLE_DESCRIPTIONS[name], permissions=[])
            db.add(role)
            existing[name] = role
        else:
            role.description = ROLE_DESCRIPTIONS[name]
    await db.flush()

    for name, codes in ROLE_PERMISSIONS.items():
        existing[name].permissions = [permissions[c] for c in codes]
    await db.flush()
    return existing


async def seed_users(db: AsyncSession, roles: dict[str, Role]) -> None:
    for spec in DEMO_USERS:
        result = await db.execute(
            select(User).options(selectinload(User.roles)).where(User.email == spec["email"])
        )
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                email=spec["email"],
                password_hash=hash_password(spec["password"]),
                display_name=spec["display_name"],
                location_id=spec["location_id"],
                roles=[roles[spec["role"]]],
                mfa_enabled=spec["mfa"],
            )
            db.add(user)
            await db.flush()
        else:
            user.roles = [roles[spec["role"]]]
            user.location_id = spec["location_id"]
            user.mfa_enabled = spec["mfa"]

        if spec["mfa"]:
            mfa_result = await db.execute(select(MfaSecret).where(MfaSecret.user_id == user.id))
            mfa_secret = mfa_result.scalar_one_or_none()
            if mfa_secret is None:
                secret = generate_totp_secret()
                db.add(MfaSecret(user_id=user.id, secret=secret))
                print(f"[seed] {spec['email']} TOTP secret (for demo/testing only): {secret}")
            else:
                print(f"[seed] {spec['email']} TOTP secret (existing): {mfa_secret.secret}")


async def main() -> None:
    async with async_session_factory() as db:
        permissions = await seed_permissions(db)
        roles = await seed_roles(db, permissions)
        await seed_users(db, roles)
        await db.commit()
    print("[seed] Done.")


if __name__ == "__main__":
    asyncio.run(main())
