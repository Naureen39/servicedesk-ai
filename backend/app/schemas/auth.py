from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"email": "manager@meridianauto.example", "password": "correct horse battery staple"}]}
    )


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    mfa_required: bool = False
    mfa_challenge_token: str | None = None


class MfaVerifyRequest(BaseModel):
    mfa_challenge_token: str
    code: str = Field(min_length=6, max_length=6)


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MeResponse(BaseModel):
    id: str
    email: str
    display_name: str | None
    roles: list[str]
    permissions: list[str]
    mfa_enabled: bool
    location_id: int | None

    model_config = ConfigDict(from_attributes=True)


class ChatSessionResponse(BaseModel):
    session_token: str
    conversation_id: str
    expires_in: int
