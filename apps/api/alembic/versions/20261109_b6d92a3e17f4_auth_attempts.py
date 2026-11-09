"""Persist rolling authentication limits across code replacement and worker processes."""

import sqlalchemy as sa

from alembic import op

revision = "b6d92a3e17f4"
down_revision = "9e4a2f0c6b71"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_attempt",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(24), nullable=False),
        sa.Column("subject_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_attempt")),
    )
    op.create_index(
        "ix_auth_attempt_scope_subject_created", "auth_attempt", ["scope", "subject_hash", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_auth_attempt_scope_subject_created", table_name="auth_attempt")
    op.drop_table("auth_attempt")
