"""Case and CaseEvent SQLAlchemy models.

Represents durable scam investigation cases and their immutable append-only event trail.
Conforms strictly to Section 4 specification and shared/api-schema.yaml contracts.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, TypeDecorator

try:
    from app.models.base import Base
except ImportError:
    from backend.app.models.base import Base


class UniversalUUID(TypeDecorator):
    """Platform-independent UUID type (uses native PG UUID or CHAR(36) on SQLite)."""

    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class UniversalJSON(TypeDecorator):
    """Platform-independent JSON type (uses JSONB on PostgreSQL, JSON on others)."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB)
        return dialect.type_descriptor(JSON)


def utc_now() -> datetime:
    """Returns timezone-aware UTC current time."""
    return datetime.now(timezone.utc)


class Case(Base):
    """Durable scam investigation case."""

    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=uuid.uuid4)
    input_type: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    is_idn: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extracted_upi_ids: Mapped[list[str]] = mapped_column(
        UniversalJSON, default=list, nullable=False
    )
    input_payee: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[str] = mapped_column(String(32), default="intake", nullable=False, index=True)
    current_stage: Mapped[str] = mapped_column(String(64), default="intake", nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    force_detonate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_seed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    streaming_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    # Relationships
    events: Mapped[list["CaseEvent"]] = relationship(
        "CaseEvent",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="CaseEvent.id",
    )


class CaseEvent(Base):
    """Append-only audit trail and live-trace event for a case."""

    __tablename__ = "case_events"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UniversalUUID,
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(
        String(32), default="info", nullable=False
    )  # info | warn | error | agent_step
    message: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(UniversalJSON, default=dict, nullable=False)

    case: Mapped["Case"] = relationship("Case", back_populates="events")
