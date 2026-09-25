from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AppointmentOut(BaseModel):
    appointment_id: str
    reference_code: str | None = None
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
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None


class SlotOfferOut(BaseModel):
    start: datetime
    end: datetime


class VehicleIn(BaseModel):
    year: int
    make: str
    model: str
    vin: str | None = None


class AppointmentCreateRequest(BaseModel):
    location_id: int
    service_code: str
    scheduled_start: datetime
    name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=7, max_length=20)
    email: str | None = None
    vehicle: VehicleIn


class AppointmentCreateResponse(BaseModel):
    appointment_id: str
    reference_code: str
    scheduled_start: datetime
    scheduled_end: datetime
    status: str


class AppointmentVerifyRequest(BaseModel):
    reference_code: str
    phone_last4: str = Field(min_length=4, max_length=4)
