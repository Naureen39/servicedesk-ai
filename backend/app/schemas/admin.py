from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str | None
    is_active: bool
    mfa_enabled: bool
    location_id: int | None
    roles: list[str]

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    display_name: str | None = None
    location_id: int | None = None
    role_names: list[str] = []


class UserPatch(BaseModel):
    is_active: bool | None = None
    location_id: int | None = None
    role_names: list[str] | None = None


class RoleOut(BaseModel):
    id: int
    name: str
    description: str | None
    permissions: list[str]

    model_config = ConfigDict(from_attributes=True)


class AuditLogOut(BaseModel):
    id: int
    actor_user_id: str | None
    action: str
    entity_type: str
    entity_id: str | None
    ip: str | None
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class KbDocumentOut(BaseModel):
    id: int
    source_path: str
    title: str | None
    document_hash: str | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class KbDocumentDetailOut(KbDocumentOut):
    content: str


class KbDocumentCreate(BaseModel):
    source_path: str
    title: str
    content: str


class KbDocumentUpdate(BaseModel):
    content: str
    title: str | None = None


class KbPublishResult(BaseModel):
    chunk_count: int
    unchanged: bool


class AppSettingsOut(BaseModel):
    llm_primary: str
    confidence_threshold: float
    cache_similarity_threshold: float
    daily_budget_groq: int
    daily_budget_gemini: int
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AppSettingsPatch(BaseModel):
    llm_primary: str | None = None
    confidence_threshold: float | None = None
    cache_similarity_threshold: float | None = None
    daily_budget_groq: int | None = None
    daily_budget_gemini: int | None = None
