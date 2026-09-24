from __future__ import annotations

from datetime import date

from pydantic import BaseModel


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
