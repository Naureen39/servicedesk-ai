"""Phase 5.2: derive bays, shift_templates, and technician_skills from the already-loaded
locations and technicians reference data (Phase 1), so the real scheduling engine has
something to compute availability against instead of the Phase 4 stub's fixed 9/11/2 slots.

- bays: one row per location per bay (locations.bay_count), typed general/lift/alignment/
  diagnostic in the same proportions service_catalog.bay_type actually needs.
- shift_templates: technicians.csv's `shift_pattern` ("Mon-Fri 07:00-15:30") expanded into one
  row per technician per working weekday.
- technician_skills: technicians.csv's `certifications` (semicolon-separated) expanded into one
  row per technician per certification, so the table is populated for real; the scheduling
  engine's actual qualification check uses technicians.skill_level vs service_catalog.
  skill_level (both A/B/C), which is the cleaner, already-available signal for that decision.

Idempotent: truncates and rebuilds all three tables from source each run.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pandas as pd
from common import REFERENCE_DIR, get_logger

logger = get_logger("build_scheduling_reference")

WEEKDAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WEEKDAY_INDEX = {name: i for i, name in enumerate(WEEKDAY_ORDER)}

# Bay type distribution per location: most bays are general-purpose; a location's bay_count
# also needs to cover alignment and diagnostic work (Section "5.2 Scheduling engine": "bay
# types"), matching service_catalog.bay_type values (general/lift/alignment/diagnostic).
BAY_TYPE_PATTERN = ["general", "general", "lift", "general", "lift", "general", "diagnostic", "general", "lift", "alignment"]


def parse_shift_pattern(pattern: str) -> list[tuple[int, str, str]]:
    """"Mon-Fri 07:00-15:30" -> [(0, "07:00", "15:30"), (1, "07:00", "15:30"), ...]."""
    match = re.match(r"(\w{3})-(\w{3})\s+(\d{2}:\d{2})-(\d{2}:\d{2})", pattern.strip())
    if not match:
        logger.warning("Could not parse shift pattern %r; skipping", pattern)
        return []
    start_day, end_day, start_time, end_time = match.groups()
    start_idx, end_idx = WEEKDAY_INDEX[start_day], WEEKDAY_INDEX[end_day]

    days = []
    idx = start_idx
    while True:
        days.append(idx)
        if idx == end_idx:
            break
        idx = (idx + 1) % 7
    return [(d, start_time, end_time) for d in days]


def build_bays(conn) -> int:
    locations = pd.read_csv(REFERENCE_DIR / "locations.csv")
    rows = []
    for loc in locations.itertuples():
        for bay_number in range(1, int(loc.bay_count) + 1):
            bay_type = BAY_TYPE_PATTERN[(bay_number - 1) % len(BAY_TYPE_PATTERN)]
            rows.append((loc.location_id, bay_number, bay_type))

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE bays RESTART IDENTITY CASCADE")
        cur.executemany("INSERT INTO bays (location_id, bay_number, bay_type) VALUES (%s, %s, %s)", rows)
    conn.commit()
    logger.info("Inserted %d bays across %d locations", len(rows), len(locations))
    return len(rows)


def build_shift_templates(conn) -> int:
    technicians = pd.read_csv(REFERENCE_DIR / "technicians.csv")
    rows = []
    for tech in technicians.itertuples():
        for weekday, start_time, end_time in parse_shift_pattern(tech.shift_pattern):
            rows.append((tech.technician_id, weekday, start_time, end_time))

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE shift_templates RESTART IDENTITY CASCADE")
        cur.executemany(
            "INSERT INTO shift_templates (technician_id, weekday, start_time, end_time) VALUES (%s, %s, %s, %s)",
            rows,
        )
    conn.commit()
    logger.info("Inserted %d shift_template rows for %d technicians", len(rows), len(technicians))
    return len(rows)


def build_holidays(conn) -> int:
    holidays = pd.read_csv(REFERENCE_DIR / "holidays.csv")
    rows = list(holidays.itertuples(index=False, name=None))

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE holidays")
        cur.executemany("INSERT INTO holidays (date, name) VALUES (%s, %s)", rows)
    conn.commit()
    logger.info("Inserted %d holidays", len(rows))
    return len(rows)


def build_technician_skills(conn) -> int:
    technicians = pd.read_csv(REFERENCE_DIR / "technicians.csv")
    rows = []
    for tech in technicians.itertuples():
        for cert in str(tech.certifications).split(";"):
            cert = cert.strip()
            if cert:
                rows.append((tech.technician_id, cert, tech.skill_level))

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE technician_skills CASCADE")
        cur.executemany(
            "INSERT INTO technician_skills (technician_id, skill_code, proficiency) VALUES (%s, %s, %s)", rows
        )
    conn.commit()
    logger.info("Inserted %d technician_skills rows", len(rows))
    return len(rows)


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL is not set")
        return 1

    import psycopg

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'bays')"
            )
            if not cur.fetchone()[0]:
                logger.warning("bays table not found (run Phase 2 Alembic migrations first)")
                return 0

        build_bays(conn)
        build_shift_templates(conn)
        build_technician_skills(conn)
        build_holidays(conn)

    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
