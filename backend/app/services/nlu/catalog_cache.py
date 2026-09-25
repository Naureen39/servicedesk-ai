"""In-memory cache of vehicle_catalog makes/models and service_catalog rows, used by slot
extraction (Section 4.1) so every message doesn't hit the database for reference data that
barely changes. Refreshed lazily on first use and on demand via `refresh()`.
"""

from __future__ import annotations

import threading

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.business import ServiceCatalog
from app.db.models.knowledge import VehicleCatalog

_lock = threading.Lock()
_makes: list[str] = []
_models_by_make: dict[str, list[str]] = {}
_service_rows: list[dict] = []
_service_embeddings: list[list[float]] | None = None
_loaded = False


async def refresh(db: AsyncSession) -> None:
    global _makes, _models_by_make, _service_rows, _service_embeddings, _loaded

    make_result = await db.execute(select(VehicleCatalog.make, VehicleCatalog.model).distinct())
    makes: set[str] = set()
    models_by_make: dict[str, set[str]] = {}
    for make, model in make_result.all():
        makes.add(make)
        models_by_make.setdefault(make, set()).add(model)

    service_result = await db.execute(select(ServiceCatalog))
    services = [
        {"code": row.code, "name": row.name, "category": row.category}
        for row in service_result.scalars().all()
    ]

    with _lock:
        _makes = sorted(makes)
        _models_by_make = {m: sorted(v) for m, v in models_by_make.items()}
        _service_rows = services
        _service_embeddings = None  # recomputed lazily on next service-type match
        _loaded = True


def is_loaded() -> bool:
    return _loaded


def get_makes() -> list[str]:
    return list(_makes)


def get_models(make: str | None = None) -> list[str]:
    if make is None:
        return sorted({m for models in _models_by_make.values() for m in models})
    return list(_models_by_make.get(make, []))


def get_service_rows() -> list[dict]:
    return list(_service_rows)


def get_or_compute_service_embeddings() -> list[list[float]]:
    global _service_embeddings
    if _service_embeddings is None:
        from app.services.embeddings import embed_passages

        texts = [f"{row['name']} ({row['category']})" for row in _service_rows]
        _service_embeddings = embed_passages(texts)
    return _service_embeddings
