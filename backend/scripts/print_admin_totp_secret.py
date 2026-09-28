"""Prints the seeded admin's TOTP secret as raw text (nothing else) so the Playwright E2E
suite can compute real login codes for the "staff login with MFA" scenario without hardcoding
a secret in the frontend repo.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.base import async_session_factory
from app.db.models.identity import MfaSecret, User


async def main() -> int:
    async with async_session_factory() as db:
        result = await db.execute(
            select(MfaSecret.secret).join(User, User.id == MfaSecret.user_id).where(User.email == "admin@meridianauto.example")
        )
        secret = result.scalar_one_or_none()
    if secret is None:
        print("no-mfa-secret-found-run-make-seed-first", file=sys.stderr)
        return 1
    print(secret)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
