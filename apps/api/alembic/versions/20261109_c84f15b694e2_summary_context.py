"""Keep summary request inputs fixed while the execution queue is pending."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "c84f15b694e2"
down_revision = "b6d92a3e17f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("result_draft", sa.Column("context_snapshot", postgresql.JSONB(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("result_draft", "context_snapshot")
