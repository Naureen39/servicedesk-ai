"""DoD: "migrations apply cleanly". Runs the full Alembic upgrade/downgrade/upgrade cycle
against a disposable database so this is verified fresh on every test run, not just once by
hand.
"""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest
from alembic.config import Config

from alembic import command

ADMIN_DSN = "postgresql://postgres:postgres@localhost:55432/postgres"
MIGRATION_TEST_DB = "meridian_migration_test"
BACKEND_DIR = Path(__file__).resolve().parents[1]


def _sync_dsn(db_name: str) -> str:
    return f"postgresql://postgres:postgres@localhost:55432/{db_name}"


@pytest.fixture
def migration_database():
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{MIGRATION_TEST_DB}"')
        conn.execute(f'CREATE DATABASE "{MIGRATION_TEST_DB}"')
    yield MIGRATION_TEST_DB
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{MIGRATION_TEST_DB}"')


def _alembic_config(db_name: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"postgresql+asyncpg://postgres:postgres@localhost:55432/{db_name}")
    return cfg


def test_migrations_apply_cleanly_and_are_reversible(migration_database):
    cfg = _alembic_config(migration_database)

    command.upgrade(cfg, "head")

    with psycopg.connect(_sync_dsn(migration_database)) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
        tables = {row[0] for row in cur.fetchall()}
    expected_tables = {"users", "roles", "permissions", "customers", "vehicles", "appointments", "repair_orders", "kb_chunks", "response_cache"}
    assert expected_tables.issubset(tables), f"missing tables: {expected_tables - tables}"

    command.downgrade(cfg, "base")

    with psycopg.connect(_sync_dsn(migration_database)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name != 'alembic_version'"
            )
            remaining = {row[0] for row in cur.fetchall()}
    assert remaining == set(), f"downgrade left tables behind: {remaining}"

    # Re-upgrade to prove the cycle is fully clean, not just one-directional.
    command.upgrade(cfg, "head")
