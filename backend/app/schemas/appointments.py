from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AppointmentOut(BaseModel):
    appointment_id: str
    customer_id: str
    vehicle_id: str
    location_id: int
    technician_id: str | None
    bay_number: int | None
    service_code: str | None
    scheduled_start: datetime
    scheduled_end: datetime
    status: str
    channel_created: str | None

    model_config = ConfigDict(from_attributes=True)


class AppointmentPatch(BaseModel):
    status: str | None = None
    technician_id: str | None = None
    bay_number: int | None = None
