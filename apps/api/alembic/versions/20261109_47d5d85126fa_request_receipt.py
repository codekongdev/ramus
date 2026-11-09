"""request receipt

Revision ID: 47d5d85126fa
Revises:
Create Date: 2026-11-09 13:01:33.720276
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "47d5d85126fa"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "request_receipt",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=100), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("response", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_request_receipt")),
        sa.UniqueConstraint(
            "actor_id",
            "scope",
            "idempotency_key",
            name=op.f("uq_request_receipt_actor_id_scope_idempotency_key"),
        ),
    )


def downgrade() -> None:
    op.drop_table("request_receipt")
