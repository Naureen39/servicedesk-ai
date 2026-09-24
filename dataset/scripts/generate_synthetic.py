"""Phase 1.5: generate 36 months of synthetic operational data (D7).

Implements the realism rules in PROJECT_PLAN Section 4.4 as independent functions (most of the
pure math lives in synthetic_rules.py so it can be unit tested). Everything here is driven by a
fixed seed (SEED = 20260924) so the dataset is reproducible from a clean clone.

Outputs (dataset/synthetic/, gitignored except *_sample.csv):
  customers.csv, vehicles.csv, appointments.csv, repair_orders.csv, ro_line_items.csv,
  payments.csv, csat_surveys.csv, conversations.jsonl, messages.jsonl, escalations.csv

Prints a validation report: row counts, null checks, referential integrity, and distribution
checks (seasonality, weekday pattern, pay-type mix) against the targets in the project plan.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from common import PROCESSED_DIR, REFERENCE_DIR, SEED, SYNTHETIC_DIR, ensure_dirs, get_logger
from faker import Faker
from synthetic_rules import (
    containment_rate,
    is_open_day,
    labor_rate_for_date,
    month_seasonality,
    no_show_probability,
    weekday_weight,
    yoy_growth_multiplier,
)

logger = get_logger("generate_synthetic")

# ---------------------------------------------------------------------------
# Volume targets (PROJECT_PLAN Section 4.4)
# ---------------------------------------------------------------------------
N_CUSTOMERS = 18_000
N_VEHICLES = 24_000
N_REPAIR_ORDERS_TARGET = 60_000
WINDOW_MONTHS = 36
CANCEL_RATE = 0.05
UPSELL_RATE = 0.22
SATURDAY_CAP = 0.90

PAY_TYPE_MIX = {"customer_pay": 0.70, "warranty": 0.18, "recall": 0.07, "internal": 0.05}

# Relative real-world frequency by service code: routine, low-cost services (oil changes,
# tire rotation) happen far more often than major services (90K service, transmission, AC
# compressor). Without this weighting a uniform service pick inflates ARO well past the
# $310-$365 target since big-ticket services would be as likely as an oil change.
SERVICE_BASE_FREQUENCY = {
    "OIL-CONV": 14, "OIL-SYN": 10, "TIRE-ROT": 12, "TIRE-REP": 3, "TIRE-REPL": 3,
    "BRAKE-PAD-F": 5, "BRAKE-PAD-R": 4, "BRAKE-ROTOR": 2, "SVC-60K": 2, "SVC-30K": 3,
    "SVC-90K": 1, "DIAG-CEL": 5, "DIAG-NOISE": 3, "AC-SVC": 5, "AC-REPAIR": 1,
    "TRANS-SVC": 2, "BATTERY-REPL": 5, "ALT-REPL": 1, "ALIGN-4W": 4, "SUSP-STRUT": 2,
    "WIPER-REPL": 4, "COOLANT-FLUSH": 3, "RECALL-SVC": 3, "STATE-INSP": 3,
}

SEASONAL_SERVICE_BOOST = {
    # month -> {service_code prefix / category: multiplier}
    "tires": {3: 1.4, 4: 1.5, 5: 1.3, 9: 1.3, 10: 1.5, 11: 1.3},
    "brakes": {3: 1.2, 4: 1.2, 5: 1.2, 9: 1.1, 10: 1.1},
    "ac": {5: 1.6, 6: 1.8, 7: 1.6, 8: 1.3},
    "battery": {12: 1.6, 1: 1.7, 2: 1.4},
}

ADVISOR_NAMES = [
    "Devon Marsh", "Karla Winters", "Trent Boyle", "Simone Ashford",
    "Yusuf Rahman", "Paige Donnelly", "Miguel Ortiz", "Leah Sutherland",
]


def rng_for(seed_offset: int) -> np.random.Generator:
    return np.random.default_rng(SEED + seed_offset)


# ---------------------------------------------------------------------------
# Reference data loading
# ---------------------------------------------------------------------------


@dataclass
class ReferenceData:
    locations: pd.DataFrame
    technicians: pd.DataFrame
    holidays: set
    service_catalog: pd.DataFrame
    labor_rate_schedule: dict
    parts_catalog: pd.DataFrame
    vehicle_catalog: pd.DataFrame
    recalls: pd.DataFrame = field(default_factory=pd.DataFrame)


def load_reference() -> ReferenceData:
    locations = pd.read_csv(REFERENCE_DIR / "locations.csv")
    technicians = pd.read_csv(REFERENCE_DIR / "technicians.csv")
    holidays_df = pd.read_csv(REFERENCE_DIR / "holidays.csv", parse_dates=["date"])
    holidays = set(holidays_df["date"].dt.date)
    service_catalog = pd.read_csv(REFERENCE_DIR / "service_catalog.csv")
    parts_catalog = pd.read_csv(REFERENCE_DIR / "parts_catalog.csv")

    labor_rates_df = pd.read_csv(REFERENCE_DIR / "labor_rates.csv", parse_dates=["effective_date"])
    schedule = {
        "customer_pay": sorted(
            (row.effective_date.date(), row.customer_pay_rate) for row in labor_rates_df.itertuples()
        ),
        "warranty": sorted(
            (row.effective_date.date(), row.warranty_rate) for row in labor_rates_df.itertuples()
        ),
        "internal": sorted(
            (row.effective_date.date(), row.internal_rate) for row in labor_rates_df.itertuples()
        ),
    }
    schedule["recall"] = schedule["warranty"]

    catalog_path = PROCESSED_DIR / "vehicle_catalog.parquet"
    if catalog_path.exists():
        vehicle_catalog = pd.read_parquet(catalog_path)
    else:
        logger.warning("vehicle_catalog.parquet missing; run build_catalog.py first. Using a tiny fallback.")
        vehicle_catalog = pd.DataFrame(
            [
                {"year": y, "make": m, "model": mo, "nhtsa_model_name": mo}
                for y in range(2015, 2024)
                for m, mo in [("Toyota", "Camry"), ("Honda", "Civic"), ("Ford", "F-150")]
            ]
        )

    recalls_path = PROCESSED_DIR / "recalls_subset.parquet"
    recalls = pd.read_parquet(recalls_path) if recalls_path.exists() else pd.DataFrame()

    return ReferenceData(
        locations=locations,
        technicians=technicians,
        holidays=holidays,
        service_catalog=service_catalog,
        labor_rate_schedule=schedule,
        parts_catalog=parts_catalog,
        vehicle_catalog=vehicle_catalog,
        recalls=recalls,
    )


def window_bounds() -> tuple[date, date]:
    end = date.today().replace(day=1)
    start_month = end.month - (WINDOW_MONTHS - 1)
    start_year = end.year
    while start_month <= 0:
        start_month += 12
        start_year -= 1
    start = date(start_year, start_month, 1)
    return start, end


# ---------------------------------------------------------------------------
# Customers and vehicles
# ---------------------------------------------------------------------------


def generate_customers(ref: ReferenceData, start: date) -> pd.DataFrame:
    fake = Faker()
    Faker.seed(SEED)
    rng = rng_for(1)

    location_ids = ref.locations["location_id"].tolist()
    location_weights = ref.locations["bay_count"] / ref.locations["bay_count"].sum()

    rows = []
    span_days = (date.today() - start).days + 365  # some customers predate the data window
    for i in range(N_CUSTOMERS):
        first = fake.first_name()
        last = fake.last_name()
        created_offset = int(rng.integers(0, span_days))
        created_at = date.today() - timedelta(days=created_offset)
        rows.append(
            {
                "customer_id": f"CUST-{i + 1:06d}",
                "first_name": first,
                "last_name": last,
                "email": f"{first.lower()}.{last.lower()}{i}@example.com",
                "phone": fake.numerify("614-555-#%%#"),
                "created_at": created_at.isoformat(),
                "preferred_location_id": int(rng.choice(location_ids, p=location_weights)),
            }
        )
    df = pd.DataFrame(rows)
    logger.info("Generated %d customers", len(df))
    return df


VIN_ALPHABET = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"  # excludes I, O, Q


def _synthetic_vin(rng: np.random.Generator) -> str:
    return "".join(rng.choice(list(VIN_ALPHABET), size=17))


def generate_vehicles(customers: pd.DataFrame, ref: ReferenceData) -> pd.DataFrame:
    fake = Faker()
    Faker.seed(SEED + 2)
    rng = rng_for(2)

    catalog = ref.vehicle_catalog
    if catalog.empty:
        raise RuntimeError("vehicle_catalog is empty; cannot generate vehicles")

    # Weight toward more recent model years for realism (older cars are underrepresented).
    year_weight = (catalog["year"] - catalog["year"].min() + 1).astype(float)
    catalog_weights = (year_weight / year_weight.sum()).to_numpy()

    # Most customers have 1 vehicle, some have 2 or 3.
    n_customers = len(customers)
    vehicles_per_customer = rng.choice([1, 2, 3], size=n_customers, p=[0.68, 0.25, 0.07])
    total_planned = vehicles_per_customer.sum()
    if total_planned > N_VEHICLES:
        # Trim deterministically until we hit the target count.
        excess = total_planned - N_VEHICLES
        idx = 0
        while excess > 0 and idx < n_customers:
            if vehicles_per_customer[idx] > 1:
                vehicles_per_customer[idx] -= 1
                excess -= 1
            idx = (idx + 1) % n_customers

    rows = []
    vehicle_seq = 1
    catalog_records = catalog.to_dict("records")
    for cust_idx, n_vehicles in enumerate(vehicles_per_customer):
        customer_id = customers.iloc[cust_idx]["customer_id"]
        for _ in range(int(n_vehicles)):
            if vehicle_seq > N_VEHICLES:
                break
            pick = catalog_records[rng.choice(len(catalog_records), p=catalog_weights)]
            rows.append(
                {
                    "vehicle_id": f"VEH-{vehicle_seq:06d}",
                    "customer_id": customer_id,
                    "year": int(pick["year"]),
                    "make": pick["make"],
                    "model": pick["model"],
                    "nhtsa_model_name": pick.get("nhtsa_model_name", pick["model"]),
                    "vin": _synthetic_vin(rng),
                    "license_plate": fake.license_plate(),
                }
            )
            vehicle_seq += 1
        if vehicle_seq > N_VEHICLES:
            break

    df = pd.DataFrame(rows)
    logger.info("Generated %d vehicles for %d customers", len(df), n_customers)
    return df


# ---------------------------------------------------------------------------
# Daily volume targets
# ---------------------------------------------------------------------------


def build_daily_location_targets(ref: ReferenceData, start: date, end: date) -> pd.DataFrame:
    days = pd.date_range(start, end + pd.offsets.MonthEnd(0), freq="D").date
    open_days = [d for d in days if is_open_day(d, ref.holidays)]

    weights = []
    for d in open_days:
        w = month_seasonality(d.month) * weekday_weight(d.weekday()) * yoy_growth_multiplier(start.year, d)
        weights.append(w)
    weights = np.array(weights)
    total_weight = weights.sum()

    total_bays = ref.locations["bay_count"].sum()
    rows = []
    for loc in ref.locations.itertuples():
        loc_share = loc.bay_count / total_bays
        for d, w in zip(open_days, weights):
            target = N_REPAIR_ORDERS_TARGET * loc_share * (w / total_weight)
            if d.weekday() == 5:  # Saturday capacity cap
                target *= SATURDAY_CAP
            rows.append({"location_id": loc.location_id, "date": d, "ro_target": target})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Appointments and repair orders
# ---------------------------------------------------------------------------


def _seasonal_category_weight(category: str, month: int) -> float:
    key = None
    lower = category.lower()
    if "tire" in lower:
        key = "tires"
    elif "brake" in lower:
        key = "brakes"
    elif "climate" in lower or "ac" in lower:
        key = "ac"
    elif "electrical" in lower:
        key = "battery"
    if key is None:
        return 1.0
    return SEASONAL_SERVICE_BOOST[key].get(month, 1.0)


def generate_appointments_and_repair_orders(
    ref: ReferenceData, customers: pd.DataFrame, vehicles: pd.DataFrame, daily_targets: pd.DataFrame
) -> dict[str, pd.DataFrame]:
    rng = rng_for(3)
    fake = Faker()
    Faker.seed(SEED + 3)

    vehicles_by_customer: dict[str, list[str]] = vehicles.groupby("customer_id")["vehicle_id"].apply(list).to_dict()
    customer_ids_with_vehicles = np.array(list(vehicles_by_customer.keys()), dtype=object)
    if len(customer_ids_with_vehicles) == 0:
        raise RuntimeError("No vehicles generated; cannot create appointments")

    # Precomputed lookups (dict/record access instead of per-row pandas filtering, which is
    # the dominant cost in a loop over tens of thousands of appointments).
    vehicles_by_id: dict[str, dict] = vehicles.set_index("vehicle_id").to_dict("index")
    service_records = ref.service_catalog.to_dict("records")
    technicians_by_location: dict[int, list[dict]] = {
        loc_id: group.to_dict("records") for loc_id, group in ref.technicians.groupby("location_id")
    }
    locations_by_id: dict[int, dict] = ref.locations.set_index("location_id").to_dict("index")
    recalls_by_make_year: dict[tuple[str, int], list[str]] = {}
    if not ref.recalls.empty:
        for (make, year), group in ref.recalls.groupby(["make", "model_year"]):
            recalls_by_make_year[(make, int(year))] = group["campaign_number"].tolist()

    appt_rows, ro_rows, line_rows, payment_rows = [], [], [], []

    appt_seq = ro_seq = line_seq = pay_seq = 1
    today = date.today()

    for row in daily_targets.itertuples():
        n_target = int(round(row.ro_target / (1 - 0.075 - CANCEL_RATE)))
        if n_target <= 0:
            continue

        loc_techs = technicians_by_location.get(row.location_id, [])
        loc_row = locations_by_id[row.location_id]

        month = row.date.month
        service_weights = np.array(
            [
                SERVICE_BASE_FREQUENCY.get(svc["code"], 1.0) * _seasonal_category_weight(svc["category"], month)
                for svc in service_records
            ]
        )
        service_weights = service_weights / service_weights.sum()

        for _ in range(n_target):
            customer_id = rng.choice(customer_ids_with_vehicles)
            vehicle_id = rng.choice(vehicles_by_customer[customer_id])
            vehicle = vehicles_by_id[vehicle_id]

            service = service_records[rng.choice(len(service_records), p=service_weights)]
            technician = loc_techs[int(rng.integers(0, len(loc_techs)))]

            lead_days = int(rng.integers(0, 30))
            booked_at = datetime.combine(row.date, datetime.min.time()) - timedelta(
                days=lead_days, hours=int(rng.integers(1, 20))
            )
            hour = int(rng.integers(7, 16))
            minute = int(rng.choice([0, 15, 30, 45]))
            scheduled_start = datetime.combine(row.date, datetime.min.time()) + timedelta(hours=hour, minutes=minute)
            duration_min = int(rng.integers(int(service["labor_hours_min"] * 60), max(int(service["labor_hours_max"] * 60), int(service["labor_hours_min"] * 60) + 15)))
            scheduled_end = scheduled_start + timedelta(minutes=duration_min)

            roll = rng.random()
            no_show_p = no_show_probability(lead_days)
            if roll < no_show_p:
                status = "no_show"
            elif roll < no_show_p + CANCEL_RATE:
                status = "cancelled"
            else:
                status = "completed"

            launch_date = today - timedelta(days=365)
            if row.date >= launch_date:
                p_assistant = containment_rate(row.date, launch_date)
                if rng.random() < p_assistant:
                    channel_created = "assistant_chat" if rng.random() < 0.75 else "assistant_voice"
                else:
                    channel_created = "phone" if rng.random() < 0.6 else "walk_in"
            else:
                channel_created = "phone" if rng.random() < 0.6 else "walk_in"

            appointment_id = f"APT-{appt_seq:07d}"
            appt_seq += 1
            bay_number = int(rng.integers(1, int(loc_row["bay_count"]) + 1))

            appt_rows.append(
                {
                    "appointment_id": appointment_id,
                    "customer_id": customer_id,
                    "vehicle_id": vehicle_id,
                    "location_id": row.location_id,
                    "technician_id": technician["technician_id"],
                    "bay_number": bay_number,
                    "service_code": service["code"],
                    "scheduled_start": scheduled_start.isoformat(),
                    "scheduled_end": scheduled_end.isoformat(),
                    "booked_at": booked_at.isoformat(),
                    "status": status,
                    "channel_created": channel_created,
                }
            )

            if status != "completed":
                continue

            pay_type = rng.choice(list(PAY_TYPE_MIX.keys()), p=list(PAY_TYPE_MIX.values()))
            recall_campaign = None
            if pay_type == "recall":
                candidates = recalls_by_make_year.get((str(vehicle["make"]).upper(), int(vehicle["year"])))
                if candidates:
                    recall_campaign = candidates[int(rng.integers(0, len(candidates)))]
                else:
                    pay_type = "warranty"

            rate = labor_rate_for_date(row.date, ref.labor_rate_schedule[pay_type])
            labor_hours = round(float(rng.uniform(service["labor_hours_min"], service["labor_hours_max"])), 2)
            labor_amount = round(labor_hours * rate, 2)

            base_parts_cost = float(rng.uniform(service["parts_cost_min"], service["parts_cost_max"])) if service["parts_cost_max"] > 0 else 0.0
            parts_amount = round(base_parts_cost, 2)

            ro_id = f"RO-{ro_seq:07d}"
            ro_seq += 1
            opened_at = scheduled_start
            closed_at = scheduled_end + timedelta(minutes=int(rng.integers(5, 45)))

            line_amount_main = labor_amount + parts_amount
            line_rows.append(
                {
                    "line_id": f"LINE-{line_seq:07d}",
                    "ro_id": ro_id,
                    "service_code": service["code"],
                    "description": service["name"],
                    "labor_hours": labor_hours,
                    "labor_amount": labor_amount,
                    "parts_amount": parts_amount,
                    "line_amount": round(line_amount_main, 2),
                    "is_upsell": False,
                }
            )
            line_seq += 1
            total_amount = line_amount_main

            if rng.random() < UPSELL_RATE:
                upsell_service = service_records[int(rng.integers(0, len(service_records)))]
                up_hours = round(float(rng.uniform(upsell_service["labor_hours_min"], upsell_service["labor_hours_max"])) * 0.6, 2)
                up_rate = labor_rate_for_date(row.date, ref.labor_rate_schedule["customer_pay"])
                up_labor = round(up_hours * up_rate, 2)
                up_parts = round(float(rng.uniform(upsell_service["parts_cost_min"], max(upsell_service["parts_cost_max"], 1))) * 0.5, 2)
                up_amount = round(up_labor + up_parts, 2)
                line_rows.append(
                    {
                        "line_id": f"LINE-{line_seq:07d}",
                        "ro_id": ro_id,
                        "service_code": upsell_service["code"],
                        "description": f"{upsell_service['name']} (inspection finding)",
                        "labor_hours": up_hours,
                        "labor_amount": up_labor,
                        "parts_amount": up_parts,
                        "line_amount": up_amount,
                        "is_upsell": True,
                    }
                )
                line_seq += 1
                total_amount += up_amount

            ro_rows.append(
                {
                    "ro_id": ro_id,
                    "appointment_id": appointment_id,
                    "customer_id": customer_id,
                    "vehicle_id": vehicle_id,
                    "location_id": row.location_id,
                    "technician_id": technician["technician_id"],
                    "opened_at": opened_at.isoformat(),
                    "closed_at": closed_at.isoformat(),
                    "pay_type": pay_type,
                    "recall_campaign_number": recall_campaign,
                    "labor_rate": rate,
                    "labor_hours": labor_hours,
                    "labor_amount": labor_amount,
                    "parts_amount": parts_amount,
                    "total_amount": round(total_amount, 2),
                    "status": "invoiced",
                }
            )

            customer_pays = pay_type == "customer_pay"
            payment_rows.append(
                {
                    "payment_id": f"PAY-{pay_seq:07d}",
                    "ro_id": ro_id,
                    "amount": round(total_amount, 2),
                    "method": (
                        rng.choice(["credit_card", "debit_card", "cash"], p=[0.7, 0.2, 0.1])
                        if customer_pays
                        else "manufacturer_reimbursement" if pay_type in ("warranty", "recall") else "internal_transfer"
                    ),
                    "paid_at": closed_at.isoformat(),
                }
            )
            pay_seq += 1

    appointments = pd.DataFrame(appt_rows)
    repair_orders = pd.DataFrame(ro_rows)
    ro_line_items = pd.DataFrame(line_rows)
    payments = pd.DataFrame(payment_rows)

    logger.info(
        "Generated %d appointments -> %d repair orders (%.1f%% completion)",
        len(appointments), len(repair_orders), 100 * len(repair_orders) / max(1, len(appointments)),
    )
    return {
        "appointments": appointments,
        "repair_orders": repair_orders,
        "ro_line_items": ro_line_items,
        "payments": payments,
    }


# ---------------------------------------------------------------------------
# CSAT
# ---------------------------------------------------------------------------


def generate_csat(repair_orders: pd.DataFrame) -> pd.DataFrame:
    rng = rng_for(4)
    rows = []
    survey_seq = 1
    scores = [5, 4, 3, 2, 1]
    score_weights = [0.55, 0.28, 0.10, 0.04, 0.03]

    for ro in repair_orders.itertuples():
        if rng.random() > 0.42:  # ~42% survey response rate
            continue
        promise_minutes = int(rng.integers(30, 240))
        wait_minutes = int(promise_minutes + rng.normal(0, 25))
        wait_minutes = max(10, wait_minutes)
        score = int(rng.choice(scores, p=score_weights))
        if wait_minutes > promise_minutes + 15:
            score = max(1, score - int(rng.integers(1, 3)))
        rows.append(
            {
                "survey_id": f"CSAT-{survey_seq:07d}",
                "ro_id": ro.ro_id,
                "customer_id": ro.customer_id,
                "score": score,
                "wait_time_minutes": wait_minutes,
                "promise_time_minutes": promise_minutes,
                "submitted_at": ro.closed_at,
            }
        )
        survey_seq += 1

    df = pd.DataFrame(rows)
    logger.info("Generated %d CSAT surveys (mean score %.2f)", len(df), df["score"].mean() if len(df) else float("nan"))
    return df


# ---------------------------------------------------------------------------
# Conversations, messages, escalations
# ---------------------------------------------------------------------------

INTENT_TEMPLATES = {
    "recall_check": ["is there a recall on my {make} {model}", "checking recall status for VIN"],
    "book_service": ["I need to book a {service}", "can I schedule an appointment"],
    "pricing_estimate": ["how much is {service}", "what's the price for an oil change"],
    "warranty_question": ["is this covered under warranty", "how long is my warranty"],
    "service_faq": ["what are your hours", "do you have a loaner car"],
    "complaint": ["I'm unhappy with my last visit", "nobody called me back"],
    "safety_concern": ["my brakes feel like they're not working", "I smell smoke from the engine"],
    "speak_to_human": ["can I talk to a real person"],
}
ESCALATION_REASONS = {
    "complaint": ("P2", 120),
    "safety_concern": ("P1", 15),
    "speak_to_human": ("P3", 24 * 60),
}


def generate_conversations_and_escalations(
    ref: ReferenceData, appointments: pd.DataFrame, customers: pd.DataFrame
) -> dict[str, pd.DataFrame]:
    rng = rng_for(5)
    today = date.today()
    launch_date = today - timedelta(days=365)

    conversations, messages, escalations = [], [], []
    conv_seq = msg_seq = esc_seq = 1

    assistant_appts = appointments[appointments["channel_created"].isin(["assistant_chat", "assistant_voice"])]
    for appt in assistant_appts.itertuples():
        conv_id = f"CONV-{conv_seq:07d}"
        conv_seq += 1
        channel = "chat" if appt.channel_created == "assistant_chat" else "voice"
        started_at = datetime.fromisoformat(appt.booked_at)
        ended_at = started_at + timedelta(minutes=int(rng.integers(2, 12)))
        conversations.append(
            {
                "conversation_id": conv_id,
                "customer_id": appt.customer_id,
                "location_id": appt.location_id,
                "channel": channel,
                "started_at": started_at.isoformat(),
                "ended_at": ended_at.isoformat(),
                "contained": True,
                "escalated": False,
                "resulting_appointment_id": appt.appointment_id,
                "intent": "book_service",
            }
        )
        msg_seq = _emit_messages(messages, conv_id, channel, "book_service", started_at, rng, msg_seq)

    # Non-booking conversations: recall checks, FAQs, pricing, complaints, safety concerns, etc.
    n_extra = int(len(assistant_appts) * 1.8)
    customer_pool = customers["customer_id"].tolist()
    location_ids = ref.locations["location_id"].tolist()
    non_booking_intents = list(INTENT_TEMPLATES.keys())

    for _ in range(n_extra):
        offset_days = int(rng.integers(0, 365))
        conv_date = today - timedelta(days=offset_days)
        p_contained = containment_rate(conv_date, launch_date)
        intent = rng.choice(non_booking_intents, p=[0.20, 0.05, 0.15, 0.15, 0.20, 0.10, 0.08, 0.07])
        channel = "chat" if rng.random() < 0.75 else "voice"
        started_at = datetime.combine(conv_date, datetime.min.time()) + timedelta(
            hours=int(rng.integers(6, 22)), minutes=int(rng.integers(0, 60))
        )
        ended_at = started_at + timedelta(minutes=int(rng.integers(1, 8)))

        escalation_forced = intent in ESCALATION_REASONS
        contained = (not escalation_forced) and (rng.random() < p_contained)
        escalated = escalation_forced or not contained

        conv_id = f"CONV-{conv_seq:07d}"
        conv_seq += 1
        conversations.append(
            {
                "conversation_id": conv_id,
                "customer_id": rng.choice(customer_pool),
                "location_id": int(rng.choice(location_ids)),
                "channel": channel,
                "started_at": started_at.isoformat(),
                "ended_at": ended_at.isoformat(),
                "contained": bool(contained),
                "escalated": bool(escalated),
                "resulting_appointment_id": None,
                "intent": intent,
            }
        )
        msg_seq = _emit_messages(messages, conv_id, channel, intent, started_at, rng, msg_seq)

        if escalated:
            priority, sla_minutes = ESCALATION_REASONS.get(intent, ("P3", 24 * 60))
            created_at = ended_at
            sla_due = created_at + timedelta(minutes=sla_minutes)
            resolved = rng.random() < 0.9
            resolved_at = created_at + timedelta(minutes=int(rng.integers(5, sla_minutes))) if resolved else None
            escalations.append(
                {
                    "escalation_id": f"ESC-{esc_seq:06d}",
                    "conversation_id": conv_id,
                    "reason": intent,
                    "priority": priority,
                    "status": "resolved" if resolved else "open",
                    "assigned_to": rng.choice(ADVISOR_NAMES),
                    "sla_due_at": sla_due.isoformat(),
                    "created_at": created_at.isoformat(),
                    "resolved_at": resolved_at.isoformat() if resolved_at else None,
                    "summary": f"Escalated {intent.replace('_', ' ')} conversation for follow-up.",
                }
            )
            esc_seq += 1

    logger.info(
        "Generated %d conversations, %d messages, %d escalations",
        len(conversations), len(messages), len(escalations),
    )
    return {
        "conversations": pd.DataFrame(conversations),
        "messages": pd.DataFrame(messages),
        "escalations": pd.DataFrame(escalations),
    }


def _emit_messages(messages: list, conv_id: str, channel: str, intent: str, started_at: datetime, rng: np.random.Generator, msg_seq: int) -> int:
    n_turns = int(rng.integers(2, 5))
    templates = INTENT_TEMPLATES.get(intent, ["hello"])
    t = started_at
    for turn in range(n_turns):
        t += timedelta(seconds=int(rng.integers(5, 40)))
        confidence = round(float(rng.uniform(0.55, 0.98)), 3)
        cache_hit = bool(rng.random() < 0.3)
        provider = None if cache_hit else str(rng.choice(["groq", "gemini", None], p=[0.6, 0.15, 0.25]))
        tokens_in = 0 if provider is None else int(rng.integers(80, 400))
        tokens_out = 0 if provider is None else int(rng.integers(20, 180))
        messages.append(
            {
                "message_id": f"MSG-{msg_seq:08d}",
                "conversation_id": conv_id,
                "turn": turn,
                "sender": "customer" if turn % 2 == 0 else "assistant",
                "text": rng.choice(templates) if turn == 0 else "[response text omitted in synthetic sample]",
                "intent": intent,
                "confidence": confidence,
                "latency_ms": int(rng.integers(80, 900)) if channel == "chat" else int(rng.integers(300, 2200)),
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "provider": provider,
                "cache_hit": cache_hit,
                "created_at": t.isoformat(),
            }
        )
        msg_seq += 1
    return msg_seq


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate(tables: dict[str, pd.DataFrame]) -> bool:
    ok = True
    logger.info("=" * 70)
    logger.info("VALIDATION REPORT")
    logger.info("=" * 70)

    for name, df in tables.items():
        logger.info("%-16s rows=%-8d nulls_per_col=%s", name, len(df), dict(df.isnull().sum()[df.isnull().sum() > 0]))

    customer_ids = set(tables["customers"]["customer_id"])
    vehicle_ids = set(tables["vehicles"]["vehicle_id"])
    appt_ids = set(tables["appointments"]["appointment_id"])
    ro_ids = set(tables["repair_orders"]["ro_id"])
    conv_ids = set(tables["conversations"]["conversation_id"])

    checks = [
        ("vehicles.customer_id", set(tables["vehicles"]["customer_id"]) - customer_ids),
        ("appointments.customer_id", set(tables["appointments"]["customer_id"]) - customer_ids),
        ("appointments.vehicle_id", set(tables["appointments"]["vehicle_id"]) - vehicle_ids),
        ("repair_orders.appointment_id", set(tables["repair_orders"]["appointment_id"]) - appt_ids),
        ("ro_line_items.ro_id", set(tables["ro_line_items"]["ro_id"]) - ro_ids),
        ("payments.ro_id", set(tables["payments"]["ro_id"]) - ro_ids),
        ("csat_surveys.ro_id", set(tables["csat_surveys"]["ro_id"]) - ro_ids),
        (
            "conversations.resulting_appointment_id",
            set(tables["conversations"]["resulting_appointment_id"].dropna()) - appt_ids,
        ),
        ("escalations.conversation_id", set(tables["escalations"]["conversation_id"]) - conv_ids),
    ]
    for label, orphans in checks:
        if orphans:
            ok = False
            logger.error("FK VIOLATION: %s has %d orphaned references (e.g. %s)", label, len(orphans), list(orphans)[:3])
        else:
            logger.info("FK OK: %s (0 violations)", label)

    ros = tables["repair_orders"]
    if len(ros):
        pay_mix = ros["pay_type"].value_counts(normalize=True).to_dict()
        logger.info("Pay type mix: %s (target %s)", {k: round(v, 3) for k, v in pay_mix.items()}, PAY_TYPE_MIX)
        for pay_type, target in PAY_TYPE_MIX.items():
            actual = pay_mix.get(pay_type, 0.0)
            if abs(actual - target) > 0.10 * target + 0.03:
                logger.warning("Pay type %s off target: actual=%.3f target=%.3f", pay_type, actual, target)

        aro = ros["total_amount"].mean()
        logger.info("Average repair order (ARO): $%.2f (target range $310-$365)", aro)

    appts = tables["appointments"]
    if len(appts):
        appts_dt = pd.to_datetime(appts["scheduled_start"])
        weekday_counts = appts_dt.dt.dayofweek.value_counts(normalize=True).sort_index()
        logger.info("Weekday distribution (0=Mon..6=Sun): %s", {int(k): round(v, 3) for k, v in weekday_counts.items()})
        no_show_rate = (appts["status"] == "no_show").mean()
        cancel_rate = (appts["status"] == "cancelled").mean()
        logger.info("No-show rate: %.3f (target 0.06-0.09), cancel rate: %.3f (target ~0.05)", no_show_rate, cancel_rate)

    logger.info("=" * 70)
    logger.info("VALIDATION %s", "PASSED" if ok else "FAILED")
    logger.info("=" * 70)
    return ok


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def write_outputs(tables: dict[str, pd.DataFrame]) -> None:
    ensure_dirs(SYNTHETIC_DIR)
    for name in ["customers", "vehicles", "appointments", "repair_orders", "ro_line_items", "payments", "csat_surveys", "escalations"]:
        df = tables[name]
        path = SYNTHETIC_DIR / f"{name}.csv"
        df.to_csv(path, index=False)
        sample_path = SYNTHETIC_DIR / f"{name}_sample.csv"
        df.head(100).to_csv(sample_path, index=False)
        logger.info("Wrote %s (%d rows) and 100-row sample", path, len(df))

    for name in ["conversations", "messages"]:
        df = tables[name]
        path = SYNTHETIC_DIR / f"{name}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for record in df.to_dict("records"):
                f.write(json.dumps(record, default=str) + "\n")
        sample_path = SYNTHETIC_DIR / f"{name}_sample.csv"
        df.head(100).to_csv(sample_path, index=False)
        logger.info("Wrote %s (%d rows) and 100-row sample", path, len(df))


def main() -> int:
    logger.info("Loading reference data")
    ref = load_reference()
    start, end = window_bounds()
    logger.info("Generation window: %s to %s (%d months)", start, end, WINDOW_MONTHS)

    customers = generate_customers(ref, start)
    vehicles = generate_vehicles(customers, ref)

    daily_targets = build_daily_location_targets(ref, start, end)
    core_tables = generate_appointments_and_repair_orders(ref, customers, vehicles, daily_targets)

    csat = generate_csat(core_tables["repair_orders"])
    conv_tables = generate_conversations_and_escalations(ref, core_tables["appointments"], customers)

    tables = {
        "customers": customers,
        "vehicles": vehicles,
        **core_tables,
        "csat_surveys": csat,
        **conv_tables,
    }

    ok = validate(tables)
    write_outputs(tables)

    if not ok:
        logger.error("Validation failed; see FK VIOLATION lines above")
        return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
