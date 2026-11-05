"""Foundations: users, sessions, invites, password resets, passkeys, audit log, API-key vault, tags.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="member"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("password_hash", sa.Text, nullable=True),
        sa.Column("colour_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed_logins", sa.Integer, nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("motion_pref", sa.String(8), nullable=False, server_default="full"),
        sa.Column("breakeven_threshold", sa.Float, nullable=False, server_default="2.0"),
        *_timestamps(),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_agent", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "invites",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("role", sa.String(16), nullable=False, server_default="member"),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_by_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_by_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "password_resets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_password_resets_user_id", "password_resets", ["user_id"])

    op.create_table(
        "passkeys",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("credential_id", sa.LargeBinary, nullable=False, unique=True),
        sa.Column("public_key", sa.LargeBinary, nullable=False),
        sa.Column("sign_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("name", sa.String(80), nullable=False, server_default="Passkey"),
        sa.Column("transports", sa.JSON, nullable=True),
        sa.Column("backed_up", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_passkeys_user_id", "passkeys", ["user_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("actor_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=True),
        sa.Column("target_id", sa.String(64), nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_log_actor_id", "audit_log", ["actor_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_at", "audit_log", ["at"])

    op.create_table(
        "user_api_keys",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary, nullable=False),
        sa.Column("last4", sa.String(4), nullable=False),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_ok", sa.Boolean, nullable=True),
        *_timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("owner_id", "provider", name="uq_user_api_keys_owner_provider"),
    )
    op.create_index("ix_user_api_keys_owner_id", "user_api_keys", ["owner_id"])

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("category", sa.String(16), nullable=False, server_default="other"),
        sa.Column("synonyms", sa.JSON, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="approved"),
        sa.Column("created_by_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("merged_into_id", sa.Integer, sa.ForeignKey("tags.id"), nullable=True),
        *_timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    for table in (
        "tags",
        "user_api_keys",
        "audit_log",
        "passkeys",
        "password_resets",
        "invites",
        "sessions",
        "users",
    ):
        op.drop_table(table)
