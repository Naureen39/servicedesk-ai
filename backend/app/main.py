from __future__ import annotations

import asyncio
import logging
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
from app.db.base import async_session_factory, engine
from app.services.embeddings import get_embedder, is_loaded
from app.services.nlu import catalog_cache

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    # Phase 3, item 1: load the embedding model once at startup (singleton), not lazily on
    # the first request, so retrieval latency is consistent from the first real query.
    logger.info("Loading embedding model %s", settings.embedding_model)
    await asyncio.to_thread(get_embedder)
    logger.info("Embedding model loaded")

    # Section 4.1: slot extraction (make/model fuzzy matching, service-type matching) reads
    # this cache; warm it at startup, same reasoning as the embedding model above.
    async with async_session_factory() as db:
        await catalog_cache.refresh(db)
    logger.info("Vehicle/service catalog cache loaded")

    # Section 8.3: the admin-editable app_settings row (provider order, confidence/cache
    # thresholds, daily budgets), cached in-process the same way.
    from app.services import settings_store

    async with async_session_factory() as db:
        await settings_store.refresh(db)
    logger.info("App settings loaded")

    # Section 4.1 models used on every turn (sentiment, intent classifier): same reasoning as
    # the embedder above. Phase 6's tight per-turn latency budget is what surfaced these as
    # cold-start-on-first-request instead of a startup cost -- the first customer turn of the
    # day was previously the one paying for it.
    from app.services.nlu import intent_classifier, sentiment

    logger.info("Loading sentiment and intent classifier models")
    await asyncio.to_thread(sentiment._load)
    await asyncio.to_thread(intent_classifier._load)
    logger.info("Sentiment and intent classifier models loaded")

    # Phase 6 item 3/5: load STT/TTS models once at startup so the first real voice turn
    # doesn't pay the model-load cost inside the DoD's per-turn latency budget.
    from app.services.voice import stt as voice_stt
    from app.services.voice import tts as voice_tts

    logger.info("Loading voice STT/TTS models")
    await asyncio.to_thread(voice_stt.warm_up)
    await asyncio.to_thread(voice_tts.warm_up)
    logger.info("Voice STT/TTS models loaded")

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

    return {
        "status": "ok",
        "database": db_status,
        "pgvector": pgvector_status,
        "embedding_model": "ok" if is_loaded() else "not_loaded",
    }
