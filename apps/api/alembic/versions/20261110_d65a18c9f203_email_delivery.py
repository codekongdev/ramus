"""Track login-mail attempts without storing plaintext codes or activating failed sends."""

import sqlalchemy as sa

from alembic import op

revision = "d65a18c9f203"
down_revision = "c84f15b694e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_code_delivery",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=True),
        sa.Column("code_id", sa.Uuid(), nullable=True),
        sa.Column("code_hash", sa.String(255), nullable=True),
        sa.Column("code_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'sending', 'failed', 'sent')", name=op.f("ck_email_code_delivery_valid_status")),
        sa.CheckConstraint("email = lower(btrim(email)) AND length(email) > 0", name=op.f("ck_email_code_delivery_normalized_email")),
        sa.CheckConstraint("(status = 'sent') = (sent_at IS NOT NULL)", name=op.f("ck_email_code_delivery_sent_timestamp")),
        sa.CheckConstraint("status = 'pending' OR (attempt_id IS NOT NULL AND code_id IS NOT NULL AND "
                           "code_hash IS NOT NULL AND code_created_at IS NOT NULL AND expires_at IS NOT NULL AND "
                           "lease_until IS NOT NULL)", name=op.f("ck_email_code_delivery_attempt_fields")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_code_delivery")),
    )
    op.create_index("ix_email_code_delivery_email_sending", "email_code_delivery", ["email"], unique=True,
                    postgresql_where=sa.text("status = 'sending'"))


def downgrade() -> None:
    # Older application versions expect a response timestamp rather than a delivery pointer.
    # Preserve accepted codes but let rolled-back clients create a compatible receipt.
    op.execute("DELETE FROM request_receipt WHERE actor_id = 'anonymous' "
               "AND scope = 'auth.email_code' AND response ? 'delivery_id'")
    op.drop_index("ix_email_code_delivery_email_sending", table_name="email_code_delivery")
    op.drop_table("email_code_delivery")
