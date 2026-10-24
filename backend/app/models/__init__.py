"""Database models package."""

try:
    from app.models.base import Base
    from app.models.case import Case, CaseEvent
except ImportError:
    from backend.app.models.base import Base
    from backend.app.models.case import Case, CaseEvent

__all__ = ["Base", "Case", "CaseEvent"]
