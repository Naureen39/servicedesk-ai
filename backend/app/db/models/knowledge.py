"""Knowledge base and vehicle/recall data tables (Section 2.1)."""

from __future__ import annotations

from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.assistant import EMBEDDING_DIM


class KbDocument(Base):
    __tablename__ = "kb_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_path: Mapped[str] = mapped_column(String(500), unique=True)
    title: Mapped[str | None] = mapped_column(String(255))
    document_hash: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")


class KbChunk(Base):
    __tablename__ = "kb_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_path: Mapped[str] = mapped_column(String(500))
    title: Mapped[str | None] = mapped_column(String(255))
    section: Mapped[str | None] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(String, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")

    # HNSW vector_cosine_ops index created in the migration (not expressible portably via ORM).


class IntentExample(Base):
    __tablename__ = "intent_examples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intent: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    utterance: Mapped[str] = mapped_column(String, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))


class RecallCampaign(Base):
    __tablename__ = "recall_campaigns"

    campaign_number: Mapped[str] = mapped_column(String(20), primary_key=True)
    make: Mapped[str] = mapped_column(String(50), primary_key=True)
    model: Mapped[str] = mapped_column(String(100), primary_key=True)
    model_year: Mapped[int] = mapped_column(Integer, primary_key=True)
    component: Mapped[str | None] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(String)
    consequence: Mapped[str | None] = mapped_column(String)
    remedy: Mapped[str | None] = mapped_column(String)
    report_date: Mapped[date | None] = mapped_column(Date)


class RecallSummary(Base):
    __tablename__ = "recall_summaries"

    campaign_number: Mapped[str] = mapped_column(String(20), primary_key=True)
    short_summary: Mapped[str | None] = mapped_column(String)
    voice_summary: Mapped[str | None] = mapped_column(String)
    provider: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")


class ComplaintsMonthly(Base):
    __tablename__ = "complaints_monthly"

    make: Mapped[str] = mapped_column(String(50), primary_key=True)
    model: Mapped[str] = mapped_column(String(100), primary_key=True)
    model_year: Mapped[int] = mapped_column(Integer, primary_key=True)
    component: Mapped[str] = mapped_column(String(255), primary_key=True)
    month: Mapped[date] = mapped_column(Date, primary_key=True)
    count: Mapped[int | None] = mapped_column(Integer)
    crash: Mapped[int | None] = mapped_column(Integer)
    fire: Mapped[int | None] = mapped_column(Integer)
    injured: Mapped[int | None] = mapped_column(Integer)


class NhtsaCache(Base):
    __tablename__ = "nhtsa_cache"

    request_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    payload: Mapped[dict | None] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")


class VehicleCatalog(Base):
    __tablename__ = "vehicle_catalog"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    make: Mapped[str] = mapped_column(String(50), primary_key=True)
    model: Mapped[str] = mapped_column(String(100), primary_key=True)
    nhtsa_model_name: Mapped[str | None] = mapped_column(String(100))
