"""Create cases and case_events tables.

Revision ID: 0001
Revises:
Create Date: 2026-10-24 16:15:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create cases table
    op.create_table(
        "cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("input_type", sa.String(length=32), nullable=False),
        sa.Column("raw_input", sa.Text(), nullable=False),
        sa.Column("normalized_url", sa.Text(), nullable=True),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("is_idn", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "extracted_upi_ids",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("input_payee", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="intake", nullable=False),
        sa.Column("current_stage", sa.String(length=64), server_default="intake", nullable=False),
        sa.Column("outcome", sa.String(length=64), nullable=True),
        sa.Column("error_reason", sa.Text(), nullable=True),
        sa.Column("force_detonate", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_seed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("streaming_url", sa.Text(), nullable=True),
        sa.Column("locked_by", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_cases_domain", "cases", ["domain"], unique=False)
    op.create_index("ix_cases_normalized_url", "cases", ["normalized_url"], unique=False)
    op.create_index("ix_cases_status", "cases", ["status"], unique=False)
    op.create_index("ix_cases_is_seed", "cases", ["is_seed"], unique=False)
    op.create_index("ix_cases_created_at", "cases", ["created_at"], unique=False)

    # 2. Create case_events table
    op.create_table(
        "case_events",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "case_id", sa.String(36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), server_default="info", nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "data",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
    )
    op.create_index("ix_case_events_case_id", "case_events", ["case_id"], unique=False)
    op.create_index("ix_case_events_ts", "case_events", ["ts"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_case_events_ts", table_name="case_events")
    op.drop_index("ix_case_events_case_id", table_name="case_events")
    op.drop_table("case_events")

    op.drop_index("ix_cases_created_at", table_name="cases")
    op.drop_index("ix_cases_is_seed", table_name="cases")
    op.drop_index("ix_cases_status", table_name="cases")
    op.drop_index("ix_cases_normalized_url", table_name="cases")
    op.drop_index("ix_cases_domain", table_name="cases")
    op.drop_table("cases")
