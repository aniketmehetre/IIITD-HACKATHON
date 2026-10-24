"""SQLAlchemy models for Campaign Correlation Intelligence Graph.

Represents mule payees, scam sites, and their confirmed vs inferred forensic edges.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.case import UniversalJSON, UniversalUUID, utc_now


class Payee(Base):
    """Mule account or fraudulent payment recipient destination."""

    __tablename__ = "payees"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    kind: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # upi | bank | wallet | qr
    value_normalized: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    case_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_seed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # Relationships
    edges: Mapped[list["Edge"]] = relationship(
        "Edge", back_populates="payee", cascade="all, delete-orphan"
    )


class Site(Base):
    """Phishing, deceptive lure, or scam portal domain."""

    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    domain: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    fingerprint: Mapped[dict[str, Any]] = mapped_column(
        UniversalJSON, default=dict, nullable=False
    )
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    is_seed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # Relationships
    edges: Mapped[list["Edge"]] = relationship(
        "Edge", back_populates="site", cascade="all, delete-orphan"
    )


class Edge(Base):
    """Forensic correlation edge linking a scam site to a payment destination."""

    __tablename__ = "edges"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    site_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payee_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("payees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UniversalUUID,
        ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    attribution: Mapped[str] = mapped_column(
        String(32), default="confirmed", nullable=False, index=True
    )  # confirmed | inferred
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(
        UniversalJSON, default=dict, nullable=False
    )
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    is_seed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # Relationships
    site: Mapped["Site"] = relationship("Site", back_populates="edges")
    payee: Mapped["Payee"] = relationship("Payee", back_populates="edges")
