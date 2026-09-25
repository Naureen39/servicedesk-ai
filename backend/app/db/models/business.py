"""Business tables: locations, customers (encrypted), vehicles, service ops (Section 2.1)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Holiday(Base):
    __tablename__ = "holidays"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    name: Mapped[str | None] = mapped_column(String(100))


class Location(Base):
    __tablename__ = "locations"

    location_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(2))
    zip: Mapped[str | None] = mapped_column(String(10))
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    timezone: Mapped[str | None] = mapped_column(String(64))
    bay_count: Mapped[int | None] = mapped_column(Integer)
    phone: Mapped[str | None] = mapped_column(String(32))
    mon_open: Mapped[str | None] = mapped_column(String(8))
    mon_close: Mapped[str | None] = mapped_column(String(8))
    tue_open: Mapped[str | None] = mapped_column(String(8))
    tue_close: Mapped[str | None] = mapped_column(String(8))
    wed_open: Mapped[str | None] = mapped_column(String(8))
    wed_close: Mapped[str | None] = mapped_column(String(8))
    thu_open: Mapped[str | None] = mapped_column(String(8))
    thu_close: Mapped[str | None] = mapped_column(String(8))
    fri_open: Mapped[str | None] = mapped_column(String(8))
    fri_close: Mapped[str | None] = mapped_column(String(8))
    sat_open: Mapped[str | None] = mapped_column(String(8))
    sat_close: Mapped[str | None] = mapped_column(String(8))
    sun_open: Mapped[str | None] = mapped_column(String(8))
    sun_close: Mapped[str | None] = mapped_column(String(8))


class Customer(Base):
    """Phone and email are stored pgcrypto-encrypted (Section 2.4); `*_hash` columns hold a
    keyed HMAC of the plaintext so the application can look customers up without decrypting
    every row. Encryption/decryption happens via pgp_sym_encrypt/pgp_sym_decrypt SQL
    functions, not in the ORM layer (see app/services/customers.py)."""

    __tablename__ = "customers"
    __table_args__ = (
        Index("ix_customers_phone_hash", "phone_hash"),
        Index("ix_customers_email_hash", "email_hash"),
    )

    customer_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    phone_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    email_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    phone_hash: Mapped[str | None] = mapped_column(String(64))
    email_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    preferred_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.location_id"))


class Vehicle(Base):
    __tablename__ = "vehicles"

    vehicle_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    year: Mapped[int | None] = mapped_column(Integer)
    make: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))
    nhtsa_model_name: Mapped[str | None] = mapped_column(String(100))
    vin: Mapped[str | None] = mapped_column(String(17))
    license_plate: Mapped[str | None] = mapped_column(String(20))


class ServiceCatalog(Base):
    __tablename__ = "service_catalog"

    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    labor_hours_min: Mapped[float | None] = mapped_column(Numeric(5, 2))
    labor_hours_max: Mapped[float | None] = mapped_column(Numeric(5, 2))
    parts_cost_min: Mapped[float | None] = mapped_column(Numeric(9, 2))
    parts_cost_max: Mapped[float | None] = mapped_column(Numeric(9, 2))
    duration_min: Mapped[int | None] = mapped_column(Integer)
    bay_type: Mapped[str | None] = mapped_column(String(30))
    skill_level: Mapped[str | None] = mapped_column(String(5))
    parts_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    """Section 5.2 business rule: "recall work requires parts availability flag" -- booking a
    service with this False is refused until parts are back in stock."""


class Technician(Base):
    __tablename__ = "technicians"

    technician_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.location_id"), index=True)
    skill_level: Mapped[str | None] = mapped_column(String(5))
    certifications: Mapped[str | None] = mapped_column(String(500))
    shift_pattern: Mapped[str | None] = mapped_column(String(100))
    hire_date: Mapped[date | None] = mapped_column(Date)
    efficiency_base: Mapped[float | None] = mapped_column(Numeric(4, 2))


class TechnicianSkill(Base):
    __tablename__ = "technician_skills"

    technician_id: Mapped[str] = mapped_column(ForeignKey("technicians.technician_id"), primary_key=True)
    skill_code: Mapped[str] = mapped_column(String(50), primary_key=True)
    proficiency: Mapped[str | None] = mapped_column(String(20))


class Bay(Base):
    __tablename__ = "bays"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.location_id"), index=True)
    bay_number: Mapped[int] = mapped_column(Integer, nullable=False)
    bay_type: Mapped[str | None] = mapped_column(String(30))


class ShiftTemplate(Base):
    __tablename__ = "shift_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    technician_id: Mapped[str] = mapped_column(ForeignKey("technicians.technician_id"), index=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[str | None] = mapped_column(String(8))
    end_time: Mapped[str | None] = mapped_column(String(8))


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (Index("ix_appointments_location_start", "location_id", "scheduled_start"),)

    appointment_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    reference_code: Mapped[str | None] = mapped_column(String(12), unique=True, index=True)
    """Customer-facing confirmation code (MRD-XXXXXX), used to look up an appointment by
    reference + phone for reschedule/cancel/status (Section 4.1 slot: reference_code)."""
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.vehicle_id"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.location_id"))
    technician_id: Mapped[str | None] = mapped_column(ForeignKey("technicians.technician_id"))
    bay_number: Mapped[int | None] = mapped_column(Integer)
    service_code: Mapped[str | None] = mapped_column(ForeignKey("service_catalog.code"))
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    booked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="booked")
    channel_created: Mapped[str | None] = mapped_column(String(30))
    booked_via_engine: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    """True only for appointments created through the Phase 5 scheduling engine's
    create_booking(), which is what the DB-enforced no-double-booking exclusion constraints
    are scoped to (see the Phase 5 migration's docstring: Phase 1's synthetic historical data
    used a simplified capacity heuristic, not real conflict-free scheduling, and already
    contains overlaps a blanket constraint could never validate against)."""


class RepairOrder(Base):
    __tablename__ = "repair_orders"
    __table_args__ = (Index("ix_repair_orders_closed_at", "closed_at"),)

    ro_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    appointment_id: Mapped[str | None] = mapped_column(ForeignKey("appointments.appointment_id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.vehicle_id"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.location_id"))
    technician_id: Mapped[str | None] = mapped_column(ForeignKey("technicians.technician_id"))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pay_type: Mapped[str | None] = mapped_column(String(20))
    recall_campaign_number: Mapped[str | None] = mapped_column(String(20))
    labor_rate: Mapped[float | None] = mapped_column(Numeric(7, 2))
    labor_hours: Mapped[float | None] = mapped_column(Numeric(6, 2))
    labor_amount: Mapped[float | None] = mapped_column(Numeric(9, 2))
    parts_amount: Mapped[float | None] = mapped_column(Numeric(9, 2))
    total_amount: Mapped[float | None] = mapped_column(Numeric(9, 2))
    status: Mapped[str] = mapped_column(String(20), default="invoiced")


class RoLineItem(Base):
    __tablename__ = "ro_line_items"

    line_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    ro_id: Mapped[str] = mapped_column(ForeignKey("repair_orders.ro_id"), index=True)
    service_code: Mapped[str | None] = mapped_column(String(30))
    description: Mapped[str | None] = mapped_column(String(255))
    labor_hours: Mapped[float | None] = mapped_column(Numeric(6, 2))
    labor_amount: Mapped[float | None] = mapped_column(Numeric(9, 2))
    parts_amount: Mapped[float | None] = mapped_column(Numeric(9, 2))
    line_amount: Mapped[float | None] = mapped_column(Numeric(9, 2))
    is_upsell: Mapped[bool] = mapped_column(Boolean, default=False)


class Part(Base):
    __tablename__ = "parts"

    part_no: Mapped[str] = mapped_column(String(30), primary_key=True)
    description: Mapped[str | None] = mapped_column(String(255))
    cost: Mapped[float | None] = mapped_column(Numeric(9, 2))
    list_price: Mapped[float | None] = mapped_column(Numeric(9, 2))
    category: Mapped[str | None] = mapped_column(String(100))


class Payment(Base):
    __tablename__ = "payments"

    payment_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    ro_id: Mapped[str] = mapped_column(ForeignKey("repair_orders.ro_id"), index=True)
    amount: Mapped[float | None] = mapped_column(Numeric(9, 2))
    method: Mapped[str | None] = mapped_column(String(40))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CsatSurvey(Base):
    __tablename__ = "csat_surveys"

    survey_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    ro_id: Mapped[str] = mapped_column(ForeignKey("repair_orders.ro_id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"))
    score: Mapped[int | None] = mapped_column(Integer)
    wait_time_minutes: Mapped[int | None] = mapped_column(Integer)
    promise_time_minutes: Mapped[int | None] = mapped_column(Integer)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ContactMessage(Base):
    """Section 7.4 Contact page: "validated form stored as a ticket"."""

    __tablename__ = "contact_messages"

    message_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.location_id"))
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
