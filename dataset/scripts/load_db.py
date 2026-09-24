"""Phase 1.6: bulk-load reference, processed, and synthetic data into PostgreSQL via COPY.

Bootstraps a minimal schema for the data-pipeline tables if they do not already exist (so
`make data` works end to end on a clean clone before the full Phase 2 Alembic migrations are
authored) and is safe to re-run against the Phase 2 schema once it exists, since it only
issues `CREATE TABLE IF NOT EXISTS` and loads by explicit column list.

Requires DATABASE_URL, e.g. postgresql://postgres:postgres@localhost:5432/meridian
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import os
import sys
from pathlib import Path

import pandas as pd
from common import PROCESSED_DIR, REFERENCE_DIR, SYNTHETIC_DIR, get_logger

logger = get_logger("load_db")

# Must match app/core/security.py:lookup_hash() in the backend exactly, so a customer inserted
# here can be found by the API's phone/email lookup. Defaults to the same dev placeholder as
# backend/.env.example; override both with the same real secret outside of development.
PII_ENCRYPTION_KEY = os.environ.get("PII_ENCRYPTION_KEY", "dev-only-pii-key-change-me")


def _lookup_hash(value: str) -> str:
    key = PII_ENCRYPTION_KEY.encode("utf-8")
    return hmac.new(key, value.strip().lower().encode("utf-8"), hashlib.sha256).hexdigest()

BOOTSTRAP_SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS locations (
    location_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT, city TEXT, state TEXT, zip TEXT,
    latitude DOUBLE PRECISION, longitude DOUBLE PRECISION,
    timezone TEXT, bay_count INTEGER, phone TEXT,
    mon_open TEXT, mon_close TEXT, tue_open TEXT, tue_close TEXT,
    wed_open TEXT, wed_close TEXT, thu_open TEXT, thu_close TEXT,
    fri_open TEXT, fri_close TEXT, sat_open TEXT, sat_close TEXT,
    sun_open TEXT, sun_close TEXT
);

CREATE TABLE IF NOT EXISTS technicians (
    technician_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    location_id INTEGER REFERENCES locations(location_id),
    skill_level TEXT, certifications TEXT, shift_pattern TEXT,
    hire_date DATE, efficiency_base NUMERIC
);

CREATE TABLE IF NOT EXISTS service_catalog (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL, category TEXT,
    labor_hours_min NUMERIC, labor_hours_max NUMERIC,
    parts_cost_min NUMERIC, parts_cost_max NUMERIC,
    duration_min INTEGER, bay_type TEXT, skill_level TEXT
);

-- Matches the Phase 2 Alembic schema: phone/email are pgcrypto-encrypted at rest, with a
-- keyed HMAC hash column for lookup (see backend/app/services/customers.py). load_customers()
-- below performs the encryption in-database via pgp_sym_encrypt; plaintext never touches a
-- Python variable beyond the CSV read.
CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    first_name TEXT, last_name TEXT,
    phone_encrypted BYTEA, email_encrypted BYTEA,
    phone_hash TEXT, email_hash TEXT,
    created_at TIMESTAMPTZ, preferred_location_id INTEGER REFERENCES locations(location_id)
);
CREATE INDEX IF NOT EXISTS ix_customers_phone_hash ON customers (phone_hash);
CREATE INDEX IF NOT EXISTS ix_customers_email_hash ON customers (email_hash);

CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_id TEXT PRIMARY KEY,
    customer_id TEXT REFERENCES customers(customer_id),
    year INTEGER, make TEXT, model TEXT, nhtsa_model_name TEXT,
    vin TEXT, license_plate TEXT
);

CREATE TABLE IF NOT EXISTS appointments (
    appointment_id TEXT PRIMARY KEY,
    customer_id TEXT REFERENCES customers(customer_id),
    vehicle_id TEXT REFERENCES vehicles(vehicle_id),
    location_id INTEGER REFERENCES locations(location_id),
    technician_id TEXT REFERENCES technicians(technician_id),
    bay_number INTEGER, service_code TEXT REFERENCES service_catalog(code),
    scheduled_start TIMESTAMPTZ, scheduled_end TIMESTAMPTZ, booked_at TIMESTAMPTZ,
    status TEXT, channel_created TEXT
);

CREATE TABLE IF NOT EXISTS repair_orders (
    ro_id TEXT PRIMARY KEY,
    appointment_id TEXT REFERENCES appointments(appointment_id),
    customer_id TEXT REFERENCES customers(customer_id),
    vehicle_id TEXT REFERENCES vehicles(vehicle_id),
    location_id INTEGER REFERENCES locations(location_id),
    technician_id TEXT REFERENCES technicians(technician_id),
    opened_at TIMESTAMPTZ, closed_at TIMESTAMPTZ,
    pay_type TEXT, recall_campaign_number TEXT,
    labor_rate NUMERIC, labor_hours NUMERIC, labor_amount NUMERIC,
    parts_amount NUMERIC, total_amount NUMERIC, status TEXT
);

CREATE TABLE IF NOT EXISTS ro_line_items (
    line_id TEXT PRIMARY KEY,
    ro_id TEXT REFERENCES repair_orders(ro_id),
    service_code TEXT, description TEXT,
    labor_hours NUMERIC, labor_amount NUMERIC, parts_amount NUMERIC, line_amount NUMERIC,
    is_upsell BOOLEAN
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id TEXT PRIMARY KEY,
    ro_id TEXT REFERENCES repair_orders(ro_id),
    amount NUMERIC, method TEXT, paid_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS csat_surveys (
    survey_id TEXT PRIMARY KEY,
    ro_id TEXT REFERENCES repair_orders(ro_id),
    customer_id TEXT REFERENCES customers(customer_id),
    score INTEGER, wait_time_minutes INTEGER, promise_time_minutes INTEGER,
    submitted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    customer_id TEXT REFERENCES customers(customer_id),
    location_id INTEGER REFERENCES locations(location_id),
    channel TEXT, started_at TIMESTAMPTZ, ended_at TIMESTAMPTZ,
    contained BOOLEAN, escalated BOOLEAN,
    resulting_appointment_id TEXT REFERENCES appointments(appointment_id),
    intent TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(conversation_id),
    turn INTEGER, sender TEXT, text TEXT, intent TEXT, confidence NUMERIC,
    latency_ms INTEGER, tokens_in INTEGER, tokens_out INTEGER,
    provider TEXT, cache_hit BOOLEAN, created_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS escalations (
    escalation_id TEXT PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(conversation_id),
    reason TEXT, priority TEXT, status TEXT, assigned_to TEXT,
    sla_due_at TIMESTAMPTZ, created_at TIMESTAMPTZ, resolved_at TIMESTAMPTZ, summary TEXT
);

CREATE TABLE IF NOT EXISTS recall_campaigns (
    campaign_number TEXT, make TEXT, model TEXT, model_year INTEGER,
    component TEXT, summary TEXT, consequence TEXT, remedy TEXT, report_date DATE,
    PRIMARY KEY (campaign_number, make, model, model_year)
);

CREATE TABLE IF NOT EXISTS complaints_monthly (
    make TEXT, model TEXT, model_year INTEGER, component TEXT, month DATE,
    count INTEGER, crash INTEGER, fire INTEGER, injured INTEGER,
    PRIMARY KEY (make, model, model_year, component, month)
);

CREATE TABLE IF NOT EXISTS vehicle_catalog (
    year INTEGER, make TEXT, model TEXT, nhtsa_model_name TEXT,
    PRIMARY KEY (year, make, model)
);

CREATE INDEX IF NOT EXISTS idx_appointments_location_start ON appointments (location_id, scheduled_start);
CREATE INDEX IF NOT EXISTS idx_repair_orders_closed_at ON repair_orders (closed_at);
CREATE INDEX IF NOT EXISTS idx_escalations_open ON escalations (status) WHERE status = 'open';
"""

# table -> (csv path, list of columns in file order, truncate-before-load)
CSV_LOAD_PLAN: list[tuple[str, Path, bool]] = [
    ("locations", REFERENCE_DIR / "locations.csv", True),
    ("technicians", REFERENCE_DIR / "technicians.csv", True),
    ("service_catalog", REFERENCE_DIR / "service_catalog.csv", True),
    # customers loaded separately by load_customers_encrypted() (needs pgp_sym_encrypt), called
    # from main() between this table and "vehicles" below so the FK dependency order holds.
]

CSV_LOAD_PLAN_AFTER_CUSTOMERS: list[tuple[str, Path, bool]] = [
    ("vehicles", SYNTHETIC_DIR / "vehicles.csv", True),
    ("appointments", SYNTHETIC_DIR / "appointments.csv", True),
    ("repair_orders", SYNTHETIC_DIR / "repair_orders.csv", True),
    ("ro_line_items", SYNTHETIC_DIR / "ro_line_items.csv", True),
    ("payments", SYNTHETIC_DIR / "payments.csv", True),
    ("csat_surveys", SYNTHETIC_DIR / "csat_surveys.csv", True),
]

# table -> (jsonl path, ordered columns)
JSONL_LOAD_PLAN: list[tuple[str, Path, list[str]]] = [
    (
        "conversations",
        SYNTHETIC_DIR / "conversations.jsonl",
        ["conversation_id", "customer_id", "location_id", "channel", "started_at", "ended_at",
         "contained", "escalated", "resulting_appointment_id", "intent"],
    ),
    (
        "messages",
        SYNTHETIC_DIR / "messages.jsonl",
        ["message_id", "conversation_id", "turn", "sender", "text", "intent", "confidence",
         "latency_ms", "tokens_in", "tokens_out", "provider", "cache_hit", "created_at"],
    ),
]

# escalations.csv must load after conversations (FK); kept separate from CSV_LOAD_PLAN.
ESCALATIONS_LOAD = ("escalations", SYNTHETIC_DIR / "escalations.csv", True)


def get_connection():
    import psycopg

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg.connect(database_url)


def bootstrap_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(BOOTSTRAP_SCHEMA_SQL)
    conn.commit()
    logger.info("Bootstrap schema applied (CREATE TABLE IF NOT EXISTS, safe to re-run)")


def copy_csv_to_table(conn, table: str, csv_path: Path, truncate: bool) -> int:
    if not csv_path.exists():
        logger.warning("%s not found, skipping table %s", csv_path, table)
        return 0

    df = pd.read_csv(csv_path)
    columns = list(df.columns)

    with conn.cursor() as cur:
        if truncate:
            cur.execute(f'TRUNCATE TABLE "{table}" CASCADE')

        buf = io.StringIO()
        df.to_csv(buf, index=False, header=False, na_rep="\\N", quoting=csv.QUOTE_MINIMAL)
        buf.seek(0)

        col_list = ", ".join(f'"{c}"' for c in columns)
        with cur.copy(f'COPY "{table}" ({col_list}) FROM STDIN WITH (FORMAT csv, NULL \'\\N\')') as copy:
            copy.write(buf.read())

    conn.commit()
    logger.info("Loaded %d rows into %s", len(df), table)
    return len(df)


def load_parquet_table(conn, table: str, parquet_path: Path, columns: list[str]) -> int:
    """Loads a processed/*.parquet file into a table already created by bootstrap_schema()."""
    if not parquet_path.exists():
        logger.warning("%s not found, skipping table %s", parquet_path, table)
        return 0
    df = pd.read_parquet(parquet_path)
    df = df[[c for c in columns if c in df.columns]]

    with conn.cursor() as cur:
        cur.execute(f'TRUNCATE TABLE "{table}" CASCADE')
        buf = io.StringIO()
        df.to_csv(buf, index=False, header=False, na_rep="\\N")
        buf.seek(0)
        col_list = ", ".join(f'"{c}"' for c in df.columns)
        with cur.copy(f'COPY "{table}" ({col_list}) FROM STDIN WITH (FORMAT csv, NULL \'\\N\')') as copy:
            copy.write(buf.read())
    conn.commit()
    logger.info("Loaded %d rows into %s", len(df), table)
    return len(df)


def load_customers_encrypted(conn, csv_path: Path = SYNTHETIC_DIR / "customers.csv") -> int:
    """Loads customers.csv with phone/email encrypted in-database via pgp_sym_encrypt, since
    COPY cannot invoke SQL functions per row. Batched with executemany for ~18k rows."""
    if not csv_path.exists():
        logger.warning("%s not found, skipping table customers", csv_path)
        return 0

    df = pd.read_csv(csv_path)
    rows = []
    for r in df.itertuples(index=False):
        phone = None if pd.isna(r.phone) else str(r.phone)
        email = None if pd.isna(r.email) else str(r.email)
        rows.append(
            (
                r.customer_id,
                None if pd.isna(r.first_name) else r.first_name,
                None if pd.isna(r.last_name) else r.last_name,
                phone,
                PII_ENCRYPTION_KEY,
                email,
                PII_ENCRYPTION_KEY,
                _lookup_hash(phone) if phone else None,
                _lookup_hash(email) if email else None,
                r.created_at,
                None if pd.isna(r.preferred_location_id) else int(r.preferred_location_id),
            )
        )

    with conn.cursor() as cur:
        cur.execute('TRUNCATE TABLE "customers" CASCADE')
        cur.executemany(
            """
            INSERT INTO customers
                (customer_id, first_name, last_name,
                 phone_encrypted, email_encrypted,
                 phone_hash, email_hash, created_at, preferred_location_id)
            VALUES
                (%s, %s, %s,
                 pgp_sym_encrypt(%s, %s), pgp_sym_encrypt(%s, %s),
                 %s, %s, %s, %s)
            """,
            rows,
        )
    conn.commit()
    logger.info("Loaded %d rows into customers (phone/email pgcrypto-encrypted)", len(rows))
    return len(rows)


def load_jsonl_to_table(conn, table: str, jsonl_path: Path, columns: list[str]) -> int:
    if not jsonl_path.exists():
        logger.warning("%s not found, skipping table %s", jsonl_path, table)
        return 0

    records = []
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    if not records:
        return 0
    df = pd.DataFrame(records)
    df = df[[c for c in columns if c in df.columns]]

    with conn.cursor() as cur:
        cur.execute(f'TRUNCATE TABLE "{table}" CASCADE')
        buf = io.StringIO()
        df.to_csv(buf, index=False, header=False, na_rep="\\N", quoting=csv.QUOTE_MINIMAL)
        buf.seek(0)
        col_list = ", ".join(f'"{c}"' for c in df.columns)
        with cur.copy(f'COPY "{table}" ({col_list}) FROM STDIN WITH (FORMAT csv, NULL \'\\N\')') as copy:
            copy.write(buf.read())
    conn.commit()
    logger.info("Loaded %d rows into %s", len(df), table)
    return len(df)


def refresh_materialized_views(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT matviewname FROM pg_matviews WHERE schemaname = 'public'
            """
        )
        views = [row[0] for row in cur.fetchall()]
    for view in views:
        with conn.cursor() as cur:
            cur.execute(f'REFRESH MATERIALIZED VIEW "{view}"')
        conn.commit()
        logger.info("Refreshed materialized view %s", view)
    if not views:
        logger.info("No materialized views present yet (created in Phase 2); nothing to refresh")


def main() -> int:
    try:
        conn = get_connection()
    except Exception as exc:
        logger.warning("Could not connect to database (%s); skipping load_db step. "
                        "Set DATABASE_URL and ensure Postgres is running to load data.", exc)
        return 0

    with conn:
        bootstrap_schema(conn)

        total = 0
        for table, csv_path, truncate in CSV_LOAD_PLAN:
            total += copy_csv_to_table(conn, table, csv_path, truncate)

        total += load_customers_encrypted(conn)

        for table, csv_path, truncate in CSV_LOAD_PLAN_AFTER_CUSTOMERS:
            total += copy_csv_to_table(conn, table, csv_path, truncate)

        for table, jsonl_path, columns in JSONL_LOAD_PLAN:
            total += load_jsonl_to_table(conn, table, jsonl_path, columns)

        esc_table, esc_path, esc_truncate = ESCALATIONS_LOAD
        total += copy_csv_to_table(conn, esc_table, esc_path, esc_truncate)

        total += load_parquet_table(
            conn, "recall_campaigns", PROCESSED_DIR / "recalls_subset.parquet",
            ["campaign_number", "make", "model", "model_year", "component", "summary", "consequence", "remedy", "report_date"],
        )
        total += load_parquet_table(
            conn, "complaints_monthly", PROCESSED_DIR / "complaints_monthly.parquet",
            ["make", "model", "model_year", "component", "month", "count", "crash", "fire", "injured"],
        )
        total += load_parquet_table(
            conn, "vehicle_catalog", PROCESSED_DIR / "vehicle_catalog.parquet",
            ["year", "make", "model", "nhtsa_model_name"],
        )

        refresh_materialized_views(conn)

    logger.info("load_db complete: %d total rows loaded", total)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
