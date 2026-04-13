"""Initial workspace store schema.

Revision ID: 001_initial
Revises: None
Create Date: 2026-04-12
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # workspace_state (legacy blob store, kept for migration compatibility)
    op.create_table(
        "workspace_state",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # workspace_session_templates
    op.create_table(
        "workspace_session_templates",
        sa.Column("role", sa.String(32), primary_key=True),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("session_status", sa.String(32), nullable=False),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("user_email", sa.String(255), nullable=False),
        sa.Column("user_name", sa.String(255), nullable=False),
        sa.Column("user_department", sa.String(255), nullable=False),
        sa.Column("avatar_initials", sa.String(16), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # workspace_issued_session_tokens
    op.create_table(
        "workspace_issued_session_tokens",
        sa.Column("token", sa.String(255), primary_key=True),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("auth_method", sa.String(64), nullable=True),
        sa.Column("session_payload", sa.JSON, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # workspace_pending_sso_states
    op.create_table(
        "workspace_pending_sso_states",
        sa.Column("state", sa.String(255), primary_key=True),
        sa.Column("scenario", sa.String(64), nullable=False),
        sa.Column("return_to", sa.Text, nullable=False),
        sa.Column("created_at_iso", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # workspace_role_policies
    op.create_table(
        "workspace_role_policies",
        sa.Column("role", sa.String(32), primary_key=True),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("requires_internal_email", sa.Boolean, nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # workspace_admin_users
    op.create_table(
        "workspace_admin_users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("scope", sa.String(64), nullable=False),
        sa.Column("last_active_at_iso", sa.String(64), nullable=False),
        sa.Column("is_internal_domain_compliant", sa.Boolean, nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_workspace_admin_users_email", "workspace_admin_users", ["email"])

    # workspace_submissions
    op.create_table(
        "workspace_submissions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("lifecycle_status", sa.String(32), nullable=False),
        sa.Column("processing_status", sa.String(32), nullable=False),
        sa.Column("linked_document_id", sa.String(64), nullable=True),
        sa.Column("visibility_scope", sa.String(32), nullable=False),
        sa.Column("created_at_iso", sa.String(64), nullable=False),
        sa.Column("updated_at_iso", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # workspace_reviews
    op.create_table(
        "workspace_reviews",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("submission_id", sa.String(64), nullable=False),
        sa.Column("published_document_id", sa.String(64), nullable=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("visibility_scope", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("reviewer_name", sa.String(255), nullable=False),
        sa.Column("created_at_iso", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_workspace_reviews_submission_id", "workspace_reviews", ["submission_id"])

    # workspace_system_settings
    op.create_table(
        "workspace_system_settings",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("group_name", sa.String(64), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("is_sensitive", sa.Boolean, nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # workspace_jobs
    op.create_table(
        "workspace_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("job_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("progress", sa.Float, nullable=False),
        sa.Column("related_title", sa.Text, nullable=False),
        sa.Column("started_at_iso", sa.String(64), nullable=False),
        sa.Column("updated_at_iso", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # workspace_audit_logs
    op.create_table(
        "workspace_audit_logs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("actor_name", sa.String(255), nullable=False),
        sa.Column("actor_role", sa.String(32), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", sa.String(128), nullable=False),
        sa.Column("target_label", sa.Text, nullable=False),
        sa.Column("created_at_iso", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # workspace_dense_audit_logs
    op.create_table(
        "workspace_dense_audit_logs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("actor_name", sa.String(255), nullable=False),
        sa.Column("actor_role", sa.String(32), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", sa.String(128), nullable=False),
        sa.Column("target_label", sa.Text, nullable=False),
        sa.Column("created_at_iso", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # workspace_documents
    op.create_table(
        "workspace_documents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("owner_email", sa.String(255), nullable=False),
        sa.Column("lifecycle_status", sa.String(32), nullable=False),
        sa.Column("processing_status", sa.String(32), nullable=False),
        sa.Column("visibility_scope", sa.String(32), nullable=False),
        sa.Column("is_archived", sa.Boolean, nullable=False),
        sa.Column("created_at_iso", sa.String(64), nullable=False),
        sa.Column("updated_at_iso", sa.String(64), nullable=False),
        sa.Column("indexed_at_iso", sa.String(64), nullable=True),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_workspace_documents_owner_email", "workspace_documents", ["owner_email"])

    # workspace_conversations
    op.create_table(
        "workspace_conversations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("updated_at_iso", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("workspace_conversations")
    op.drop_index("ix_workspace_documents_owner_email", table_name="workspace_documents")
    op.drop_table("workspace_documents")
    op.drop_table("workspace_dense_audit_logs")
    op.drop_table("workspace_audit_logs")
    op.drop_table("workspace_jobs")
    op.drop_table("workspace_system_settings")
    op.drop_index("ix_workspace_reviews_submission_id", table_name="workspace_reviews")
    op.drop_table("workspace_reviews")
    op.drop_table("workspace_submissions")
    op.drop_index("ix_workspace_admin_users_email", table_name="workspace_admin_users")
    op.drop_table("workspace_admin_users")
    op.drop_table("workspace_role_policies")
    op.drop_table("workspace_pending_sso_states")
    op.drop_table("workspace_issued_session_tokens")
    op.drop_table("workspace_session_templates")
    op.drop_table("workspace_state")
