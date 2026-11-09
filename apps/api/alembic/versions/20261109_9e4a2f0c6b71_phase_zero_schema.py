"""phase zero schema

Revision ID: 9e4a2f0c6b71
Revises: 47d5d85126fa
Create Date: 2026-11-09 13:36:03.684665
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "9e4a2f0c6b71"
down_revision: str | None = "47d5d85126fa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "email = lower(btrim(email)) AND length(email) > 0", name=op.f("ck_account_normalized_email")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account")),
        sa.UniqueConstraint("email", name=op.f("uq_account_email")),
    )
    op.create_table(
        "email_code",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("attempts BETWEEN 0 AND 5", name=op.f("ck_email_code_valid_attempts")),
        sa.CheckConstraint(
            "email = lower(btrim(email)) AND length(email) > 0", name=op.f("ck_email_code_normalized_email")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_code")),
    )
    op.create_index("ix_email_code_email_created_at", "email_code", ["email", "created_at"], unique=False)
    op.create_table(
        "project",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_shared_sample", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("seed_key", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project")),
        sa.UniqueConstraint("seed_key", name=op.f("uq_project_seed_key")),
    )
    op.create_table(
        "seed_marker",
        sa.Column("key", sa.String(length=200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("version > 0", name=op.f("ck_seed_marker_positive_version")),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_seed_marker")),
    )
    op.create_table(
        "ai_connection",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("provider = 'openai'", name=op.f("ck_ai_connection_valid_provider")),
        sa.CheckConstraint("status IN ('connected', 'invalid')", name=op.f("ck_ai_connection_valid_status")),
        sa.CheckConstraint("length(ciphertext) > 0", name=op.f("ck_ai_connection_ciphertext_not_empty")),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_ai_connection_account_id_account")
        ),
        sa.PrimaryKeyConstraint("account_id", name=op.f("pk_ai_connection")),
    )
    op.create_table(
        "conversation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("seed_key", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "origin IN ('top', 'branch', 'from_result')", name=op.f("ck_conversation_valid_origin")
        ),
        sa.CheckConstraint(
            "parent_id IS NULL OR parent_id <> id", name=op.f("ck_conversation_not_own_parent")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["account.id"], name=op.f("fk_conversation_created_by_account")
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["conversation.id"], name=op.f("fk_conversation_parent_id_conversation")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name=op.f("fk_conversation_project_id_project")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversation")),
    )
    op.create_index("ix_conversation_project_id_title", "conversation", ["project_id", "title"], unique=False)
    op.create_table(
        "membership",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role = 'editor'", name=op.f("ck_membership_valid_role")),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_membership_account_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name=op.f("fk_membership_project_id_project")
        ),
        sa.PrimaryKeyConstraint("account_id", "project_id", name=op.f("pk_membership")),
    )
    op.create_table(
        "resource",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("latest_revision_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("seed_key", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('skill', 'text', 'file')", name=op.f("ck_resource_valid_kind")),
        sa.ForeignKeyConstraint(["created_by"], ["account.id"], name=op.f("fk_resource_created_by_account")),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], name=op.f("fk_resource_project_id_project")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resource")),
    )
    op.create_table(
        "session",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], name=op.f("fk_session_account_id_account")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_session")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_session_token_hash")),
    )
    op.create_table(
        "message",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("author_kind", sa.String(length=16), nullable=False),
        sa.Column("author_account_id", sa.Uuid(), nullable=True),
        sa.Column("example_author_label", sa.String(length=100), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "author_kind IN ('human', 'ai', 'system')", name=op.f("ck_message_valid_author_kind")
        ),
        sa.CheckConstraint("length(btrim(body)) BETWEEN 1 AND 20000", name=op.f("ck_message_valid_body")),
        sa.CheckConstraint("seq > 0", name=op.f("ck_message_positive_seq")),
        sa.ForeignKeyConstraint(
            ["author_account_id"], ["account.id"], name=op.f("fk_message_author_account_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversation.id"], name=op.f("fk_message_conversation_id_conversation")
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["account.id"], name=op.f("fk_message_requested_by_account")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_message")),
        sa.UniqueConstraint("conversation_id", "seq", name=op.f("uq_message_conversation_id_seq")),
    )
    op.create_table(
        "resource_revision",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("base_revision_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "(instructions IS NOT NULL AND content IS NULL AND file_name IS NULL) OR (instructions IS NULL AND content IS NOT NULL)",
            name=op.f("ck_resource_revision_valid_content"),
        ),
        sa.CheckConstraint(
            "(number = 1 AND base_revision_id IS NULL) OR (number > 1 AND base_revision_id IS NOT NULL)",
            name=op.f("ck_resource_revision_number_has_base"),
        ),
        sa.CheckConstraint(
            "base_revision_id IS NULL OR base_revision_id <> id",
            name=op.f("ck_resource_revision_not_own_base"),
        ),
        sa.CheckConstraint("number > 0", name=op.f("ck_resource_revision_positive_number")),
        sa.ForeignKeyConstraint(
            ["base_revision_id", "resource_id"],
            ["resource_revision.id", "resource_revision.resource_id"],
            name="fk_resource_revision_base",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["account.id"], name=op.f("fk_resource_revision_created_by_account")
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"], ["resource.id"], name=op.f("fk_resource_revision_resource_id_resource")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resource_revision")),
        sa.UniqueConstraint("id", "resource_id", name=op.f("uq_resource_revision_id_resource_id")),
        sa.UniqueConstraint("resource_id", "number", name=op.f("uq_resource_revision_resource_id_number")),
    )
    op.create_table(
        "task",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_conversation_id", sa.Uuid(), nullable=False),
        sa.Column("child_conversation_id", sa.Uuid(), nullable=False),
        sa.Column("source_run_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("current_run_id", sa.Uuid(), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_params", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'ready', 'failed', 'cancelled')",
            name=op.f("ck_task_valid_status"),
        ),
        sa.CheckConstraint(
            "source_conversation_id <> child_conversation_id", name=op.f("ck_task_distinct_conversations")
        ),
        sa.ForeignKeyConstraint(
            ["child_conversation_id"],
            ["conversation.id"],
            name=op.f("fk_task_child_conversation_id_conversation"),
        ),
        sa.ForeignKeyConstraint(["requested_by"], ["account.id"], name=op.f("fk_task_requested_by_account")),
        sa.ForeignKeyConstraint(
            ["source_conversation_id"],
            ["conversation.id"],
            name=op.f("fk_task_source_conversation_id_conversation"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task")),
        sa.UniqueConstraint("child_conversation_id", name=op.f("uq_task_child_conversation_id")),
        sa.UniqueConstraint("source_run_id", "ordinal", name=op.f("uq_task_source_run_id_ordinal")),
    )
    op.create_table(
        "conversation_resource",
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("applied_by", sa.Uuid(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["applied_by"], ["account.id"], name=op.f("fk_conversation_resource_applied_by_account")
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversation.id"],
            name=op.f("fk_conversation_resource_conversation_id_conversation"),
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"], ["resource.id"], name=op.f("fk_conversation_resource_resource_id_resource")
        ),
        sa.ForeignKeyConstraint(
            ["revision_id", "resource_id"],
            ["resource_revision.id", "resource_revision.resource_id"],
            name="fk_conversation_resource_pinned_revision",
        ),
        sa.PrimaryKeyConstraint("conversation_id", "resource_id", name=op.f("pk_conversation_resource")),
    )
    op.create_table(
        "result",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_conversation_id", sa.Uuid(), nullable=False),
        sa.Column("source_task_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("latest_revision_id", sa.Uuid(), nullable=True),
        sa.Column("latest_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "(latest_revision_id IS NULL AND latest_version = 0) OR (latest_revision_id IS NOT NULL AND latest_version > 0)",
            name=op.f("ck_result_valid_latest_version"),
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], name=op.f("fk_result_project_id_project")),
        sa.ForeignKeyConstraint(
            ["source_conversation_id"],
            ["conversation.id"],
            name=op.f("fk_result_source_conversation_id_conversation"),
        ),
        sa.ForeignKeyConstraint(["source_task_id"], ["task.id"], name=op.f("fk_result_source_task_id_task")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_result")),
        sa.UniqueConstraint("source_task_id", name=op.f("uq_result_source_task_id")),
    )
    op.create_table(
        "run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("credential_account_id", sa.Uuid(), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("attempt", sa.Integer(), server_default="1", nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_params", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "(purpose = 'work' AND target_id IS NULL) OR (purpose = 'summary' AND target_id IS NOT NULL)",
            name=op.f("ck_run_purpose_target"),
        ),
        sa.CheckConstraint("jsonb_typeof(input_snapshot) = 'object'", name=op.f("ck_run_snapshot_is_object")),
        sa.CheckConstraint("purpose IN ('work', 'summary')", name=op.f("ck_run_valid_purpose")),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')",
            name=op.f("ck_run_valid_status"),
        ),
        sa.CheckConstraint("attempt > 0", name=op.f("ck_run_positive_attempt")),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversation.id"], name=op.f("fk_run_conversation_id_conversation")
        ),
        sa.ForeignKeyConstraint(
            ["credential_account_id"], ["account.id"], name=op.f("fk_run_credential_account_id_account")
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], name=op.f("fk_run_project_id_project")),
        sa.ForeignKeyConstraint(["requested_by"], ["account.id"], name=op.f("fk_run_requested_by_account")),
        sa.ForeignKeyConstraint(["task_id"], ["task.id"], name=op.f("fk_run_task_id_task")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_run")),
    )
    op.create_index("ix_run_status_created_at", "run", ["status", "created_at"], unique=False)
    op.create_index(
        "uq_run_active_summary_target",
        "run",
        ["target_id"],
        unique=True,
        postgresql_where=sa.text("purpose = 'summary' AND status IN ('pending', 'running')"),
    )
    op.create_index(
        "uq_run_active_work_conversation",
        "run",
        ["conversation_id"],
        unique=True,
        postgresql_where=sa.text("purpose = 'work' AND status IN ('pending', 'running')"),
    )
    op.create_table(
        "result_draft",
        sa.Column("result_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("conclusion", sa.Text(), nullable=True),
        sa.Column("base_version", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("message_from_seq", sa.BigInteger(), nullable=False),
        sa.Column("message_to_seq", sa.BigInteger(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_params", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('generating', 'ready', 'failed')", name=op.f("ck_result_draft_valid_status")
        ),
        sa.CheckConstraint("base_version >= 0", name=op.f("ck_result_draft_nonnegative_base_version")),
        sa.CheckConstraint(
            "message_from_seq > 0 AND message_to_seq >= message_from_seq",
            name=op.f("ck_result_draft_valid_message_range"),
        ),
        sa.ForeignKeyConstraint(["result_id"], ["result.id"], name=op.f("fk_result_draft_result_id_result")),
        sa.ForeignKeyConstraint(["run_id"], ["run.id"], name=op.f("fk_result_draft_run_id_run")),
        sa.PrimaryKeyConstraint("result_id", name=op.f("pk_result_draft")),
    )
    op.create_table(
        "result_revision",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("result_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("conclusion", sa.Text(), nullable=False),
        sa.Column("source", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("saved_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "jsonb_typeof(source) = 'object'", name=op.f("ck_result_revision_source_is_object")
        ),
        sa.CheckConstraint(
            "length(btrim(conclusion)) BETWEEN 1 AND 20000", name=op.f("ck_result_revision_valid_conclusion")
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_result_revision_positive_version")),
        sa.ForeignKeyConstraint(
            ["result_id"], ["result.id"], name=op.f("fk_result_revision_result_id_result")
        ),
        sa.ForeignKeyConstraint(
            ["saved_by"], ["account.id"], name=op.f("fk_result_revision_saved_by_account")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_result_revision")),
        sa.UniqueConstraint(
            "id", "result_id", "version", name=op.f("uq_result_revision_id_result_id_version")
        ),
        sa.UniqueConstraint("result_id", "version", name=op.f("uq_result_revision_result_id_version")),
    )
    op.create_table(
        "conversation_input",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("result_id", sa.Uuid(), nullable=False),
        sa.Column("result_revision_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title_snapshot", sa.String(length=100), nullable=False),
        sa.Column("conclusion_snapshot", sa.Text(), nullable=False),
        sa.Column("source_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("origin", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "jsonb_typeof(source_snapshot) = 'object'",
            name=op.f("ck_conversation_input_source_snapshot_is_object"),
        ),
        sa.CheckConstraint(
            "origin IN ('share', 'new_conversation')", name=op.f("ck_conversation_input_valid_origin")
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversation.id"],
            name=op.f("fk_conversation_input_conversation_id_conversation"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["account.id"], name=op.f("fk_conversation_input_created_by_account")
        ),
        sa.ForeignKeyConstraint(
            ["result_id"], ["result.id"], name=op.f("fk_conversation_input_result_id_result")
        ),
        sa.ForeignKeyConstraint(
            ["result_revision_id", "result_id", "version"],
            ["result_revision.id", "result_revision.result_id", "result_revision.version"],
            name="fk_conversation_input_pinned_revision",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversation_input")),
        sa.UniqueConstraint(
            "conversation_id", "result_id", name=op.f("uq_conversation_input_conversation_id_result_id")
        ),
    )
    op.create_table(
        "share",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("result_revision_id", sa.Uuid(), nullable=False),
        sa.Column("target_conversation_id", sa.Uuid(), nullable=False),
        sa.Column("shared_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["result_revision_id"],
            ["result_revision.id"],
            name=op.f("fk_share_result_revision_id_result_revision"),
        ),
        sa.ForeignKeyConstraint(["shared_by"], ["account.id"], name=op.f("fk_share_shared_by_account")),
        sa.ForeignKeyConstraint(
            ["target_conversation_id"],
            ["conversation.id"],
            name=op.f("fk_share_target_conversation_id_conversation"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_share")),
        sa.UniqueConstraint(
            "result_revision_id",
            "target_conversation_id",
            name=op.f("uq_share_result_revision_id_target_conversation_id"),
        ),
    )
    # Add cyclic references only after all tables exist.
    op.create_foreign_key(
        "fk_conversation_task_id_task",
        "conversation",
        "task",
        ["task_id"],
        ["id"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_foreign_key(
        "fk_resource_latest_revision",
        "resource",
        "resource_revision",
        ["latest_revision_id", "id"],
        ["id", "resource_id"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_foreign_key("fk_message_run_id_run", "message", "run", ["run_id"], ["id"])
    op.create_foreign_key("fk_task_current_run_id_run", "task", "run", ["current_run_id"], ["id"])
    op.create_foreign_key("fk_task_source_run_id_run", "task", "run", ["source_run_id"], ["id"])
    op.create_foreign_key(
        "fk_result_latest_revision",
        "result",
        "result_revision",
        ["latest_revision_id", "id", "latest_version"],
        ["id", "result_id", "version"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_foreign_key("fk_run_target_id_result", "run", "result", ["target_id"], ["id"])


def downgrade() -> None:
    # Remove cyclic references before reverse-order table drops.
    op.drop_constraint("fk_conversation_task_id_task", "conversation", type_="foreignkey")
    op.drop_constraint("fk_resource_latest_revision", "resource", type_="foreignkey")
    op.drop_constraint("fk_message_run_id_run", "message", type_="foreignkey")
    op.drop_constraint("fk_task_current_run_id_run", "task", type_="foreignkey")
    op.drop_constraint("fk_task_source_run_id_run", "task", type_="foreignkey")
    op.drop_constraint("fk_result_latest_revision", "result", type_="foreignkey")
    op.drop_constraint("fk_run_target_id_result", "run", type_="foreignkey")
    op.drop_table("share")
    op.drop_table("conversation_input")
    op.drop_table("result_revision")
    op.drop_table("result_draft")
    op.drop_index(
        "uq_run_active_work_conversation",
        table_name="run",
        postgresql_where=sa.text("purpose = 'work' AND status IN ('pending', 'running')"),
    )
    op.drop_index(
        "uq_run_active_summary_target",
        table_name="run",
        postgresql_where=sa.text("purpose = 'summary' AND status IN ('pending', 'running')"),
    )
    op.drop_index("ix_run_status_created_at", table_name="run")
    op.drop_table("run")
    op.drop_table("result")
    op.drop_table("conversation_resource")
    op.drop_table("task")
    op.drop_table("resource_revision")
    op.drop_table("message")
    op.drop_table("session")
    op.drop_table("resource")
    op.drop_table("membership")
    op.drop_index("ix_conversation_project_id_title", table_name="conversation")
    op.drop_table("conversation")
    op.drop_table("ai_connection")
    op.drop_table("seed_marker")
    op.drop_table("project")
    op.drop_index("ix_email_code_email_created_at", table_name="email_code")
    op.drop_table("email_code")
    op.drop_table("account")
