from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import RequestIdMiddleware, configure_logging
from app.core.rate_limit import limiter
from app.core.security_headers import SecurityHeadersMiddleware
from app.db.base import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    yield
    await engine.dispose()


app = FastAPI(title="Meridian Assist API", version="0.1.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda request, exc: _rate_limit_handler(request, exc))
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(api_router)


def _rate_limit_handler(request, exc):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=429,
        content={
            "type": "https://meridian.example/problems/rate-limited",
            "title": "Too Many Requests",
            "status": 429,
            "detail": "Rate limit exceeded",
        },
        media_type="application/problem+json",
    )


@app.get("/api/v1/health")
async def health() -> dict:
    db_status = "unknown"
    pgvector_status = "unknown"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_status = "ok"
            result = await conn.execute(
                text("SELECT EXISTS (SELECT FROM pg_extension WHERE extname = 'vector')")
            )
            pgvector_status = "ok" if result.scalar() else "not_installed"
    except Exception as exc:  # pragma: no cover - depends on live infra
        db_status = f"error: {exc}"

    return {"status": "ok", "database": db_status, "pgvector": pgvector_status}
