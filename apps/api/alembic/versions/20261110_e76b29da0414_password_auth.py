"""Add password credentials without claiming existing email-code accounts."""

import sqlalchemy as sa

from alembic import op

revision = "e76b29da0414"
down_revision = "d65a18c9f203"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("account", sa.Column("password_hash", sa.String(255), nullable=True))


def downgrade() -> None:
    op.execute("DELETE FROM request_receipt WHERE scope IN ('auth.register', 'auth.password_login') "
               "OR left(scope, length('access.password_setup:')) = 'access.password_setup:'")
    op.drop_column("account", "password_hash")
