"""Import every model module so Base.metadata is fully populated for Alembic autogenerate."""

from app.db.models import assistant, business, identity, knowledge

__all__ = ["assistant", "business", "identity", "knowledge"]
