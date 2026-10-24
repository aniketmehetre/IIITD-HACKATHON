"""SQLAlchemy models for Immutable Hash-Chained Evidence Ledger."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.case import UniversalUUID, utc_now


class EvidenceLedger(Base):
    """Immutable, append-only hash-chained ledger sealing generated evidence dossiers."""

    __tablename__ = "evidence_ledger"

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
    pdf_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    bundle_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    signature: Mapped[str] = mapped_column(String(128), nullable=False)
    prev_entry_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
