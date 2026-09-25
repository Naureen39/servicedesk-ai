from __future__ import annotations

from datetime import date

from pydantic import BaseModel, EmailStr, Field


class RecallOut(BaseModel):
    campaign_number: str
    make: str
    model: str
    model_year: int
    component: str | None
    summary: str | None
    consequence: str | None
    remedy: str | None
    report_date: date | None


class ComplaintSummaryOut(BaseModel):
    make: str
    model: str
    model_year: int
    component: str
    total_count: int
    crash_count: int
    fire_count: int
    injured_count: int


class LocationOut(BaseModel):
    location_id: int
    name: str
    address: str | None
    city: str | None
    state: str | None
    zip: str | None
    latitude: float | None
    longitude: float | None
    timezone: str | None
    phone: str | None
    mon_open: str | None
    mon_close: str | None
    tue_open: str | None
    tue_close: str | None
    wed_open: str | None
    wed_close: str | None
    thu_open: str | None
    thu_close: str | None
    fri_open: str | None
    fri_close: str | None
    sat_open: str | None
    sat_close: str | None
    sun_open: str | None
    sun_close: str | None

    model_config = {"from_attributes": True}


class ServiceCatalogOut(BaseModel):
    code: str
    name: str
    category: str | None
    labor_hours_min: float | None
    labor_hours_max: float | None
    parts_cost_min: float | None
    parts_cost_max: float | None
    duration_min: int | None
    parts_available: bool

    model_config = {"from_attributes": True}


class LiveRecallOut(BaseModel):
    campaign_number: str
    component: str
    summary: str
    consequence: str
    remedy: str
    report_date: str


class VehicleAmbiguousOut(BaseModel):
    candidates: list[str]


class ContactRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=32)
    location_id: int | None = None
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=5000)


class ContactResponse(BaseModel):
    message_id: str
    status: str
