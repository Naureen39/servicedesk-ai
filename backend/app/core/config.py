"""Application settings, loaded from environment variables / .env (Section 3.3 of the plan)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database ---
    database_url: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/meridian")

    # --- Auth ---
    jwt_secret: str = Field(default="change-me-dev-only")
    jwt_refresh_secret: str = Field(default="change-me-dev-only")
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7
    anonymous_session_ttl_minutes: int = 30
    account_lockout_threshold: int = 5
    account_lockout_minutes: int = 15

    # --- PII / column encryption ---
    pii_encryption_key: str = Field(default="change-me-dev-only")

    # --- LLM providers (Phase 4, referenced by settings only) ---
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    llm_primary: str = "groq"
    llm_daily_request_budget_groq: int = 900
    llm_daily_request_budget_gemini: int = 1400

    # --- Retrieval (Phase 3) ---
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    # --- Voice (Phase 6) ---
    stt_model: str = "small.en"
    tts_voice: str = "af_heart"

    # --- CORS ---
    cors_origins: str = "http://localhost:5173"

    # --- Rate limits (Section 2.4) ---
    rate_limit_chat_per_minute: int = 20
    rate_limit_login_per_minute: int = 10

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
