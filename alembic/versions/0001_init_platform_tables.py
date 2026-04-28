"""init platform tables

Revision ID: 0001_init_platform_tables
Revises:
Create Date: 2026-04-25

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_init_platform_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leadpage_users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_ts", sa.Integer(), nullable=False),
    )
    op.create_index("ix_leadpage_users_email", "leadpage_users", ["email"], unique=True)

    op.create_table(
        "leadpage_providers",
        sa.Column("provider", sa.String(length=80), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("created_ts", sa.Integer(), nullable=False),
    )
    op.create_index("ix_leadpage_providers_owner_user_id", "leadpage_providers", ["owner_user_id"])

    op.create_table(
        "leadpage_provider_secrets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("secret_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_ts", sa.Integer(), nullable=False),
        sa.Column("disabled_ts", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_leadpage_provider_secrets_provider", "leadpage_provider_secrets", ["provider"]
    )

    op.create_table(
        "leadpage_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("run_id", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("ticker", sa.String(length=80), nullable=True),
        sa.Column("total_return_pct", sa.Float(), nullable=True),
        sa.Column("sharpe", sa.Float(), nullable=True),
        sa.Column("max_drawdown_pct", sa.Float(), nullable=True),
        sa.Column("trade_count", sa.Integer(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
    )
    op.create_index("ix_leadpage_results_provider", "leadpage_results", ["provider"])

    op.create_table(
        "leadpage_signals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.String(length=8000), nullable=False),
        sa.Column("ticker", sa.String(length=80), nullable=True),
        sa.Column("result_provider", sa.String(length=80), nullable=True),
        sa.Column("result_run_id", sa.String(length=160), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
    )
    op.create_index("ix_leadpage_signals_provider", "leadpage_signals", ["provider"])
    op.create_index("ix_leadpage_signals_ts", "leadpage_signals", ["ts"])

    op.create_table(
        "leadpage_nonces",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("nonce", sa.String(length=120), nullable=False),
        sa.UniqueConstraint("provider", "nonce", name="uq_provider_nonce"),
    )
    op.create_index("ix_leadpage_nonces_provider", "leadpage_nonces", ["provider"])

    op.create_table(
        "leadpage_follows",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.UniqueConstraint("user_id", "provider", name="uq_follow_user_provider"),
    )
    op.create_index("ix_leadpage_follows_user_id", "leadpage_follows", ["user_id"])
    op.create_index("ix_leadpage_follows_provider", "leadpage_follows", ["provider"])

    op.create_table(
        "leadpage_inbox",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("signal_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.String(length=8000), nullable=False),
        sa.Column("ticker", sa.String(length=80), nullable=True),
        sa.Column("read_ts", sa.Integer(), nullable=True),
        sa.UniqueConstraint("user_id", "signal_id", name="uq_inbox_user_signal"),
    )
    op.create_index("ix_leadpage_inbox_user_id", "leadpage_inbox", ["user_id"])
    op.create_index("ix_leadpage_inbox_signal_id", "leadpage_inbox", ["signal_id"])
    op.create_index("ix_leadpage_inbox_provider", "leadpage_inbox", ["provider"])
    op.create_index("ix_leadpage_inbox_ts", "leadpage_inbox", ["ts"])

    op.create_table(
        "leadpage_fanout_cursor",
        sa.Column("name", sa.String(length=80), primary_key=True),
        sa.Column("last_signal_id", sa.Integer(), nullable=False),
        sa.Column("updated_ts", sa.Integer(), nullable=False),
    )

    op.create_table(
        "leadpage_copy_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("auto_execute", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("instrument", sa.String(length=16), nullable=False, server_default="spot"),
        sa.Column("max_notional_usdt", sa.Float(), nullable=True),
        sa.UniqueConstraint("user_id", "provider", name="uq_copy_user_provider"),
    )
    op.create_index("ix_leadpage_copy_settings_user_id", "leadpage_copy_settings", ["user_id"])
    op.create_index("ix_leadpage_copy_settings_provider", "leadpage_copy_settings", ["provider"])

    op.create_table(
        "leadpage_executions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("signal_id", sa.Integer(), nullable=False),
        sa.Column("inbox_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("detail", sa.String(length=2000), nullable=False),
        sa.Column("trade", sa.JSON(), nullable=True),
    )
    op.create_index("ix_leadpage_executions_user_id", "leadpage_executions", ["user_id"])
    op.create_index("ix_leadpage_executions_provider", "leadpage_executions", ["provider"])
    op.create_index("ix_leadpage_executions_signal_id", "leadpage_executions", ["signal_id"])
    op.create_index("ix_leadpage_executions_ts", "leadpage_executions", ["ts"])


def downgrade() -> None:
    op.drop_index("ix_leadpage_executions_ts", table_name="leadpage_executions")
    op.drop_index("ix_leadpage_executions_signal_id", table_name="leadpage_executions")
    op.drop_index("ix_leadpage_executions_provider", table_name="leadpage_executions")
    op.drop_index("ix_leadpage_executions_user_id", table_name="leadpage_executions")
    op.drop_table("leadpage_executions")

    op.drop_index("ix_leadpage_copy_settings_provider", table_name="leadpage_copy_settings")
    op.drop_index("ix_leadpage_copy_settings_user_id", table_name="leadpage_copy_settings")
    op.drop_table("leadpage_copy_settings")

    op.drop_table("leadpage_fanout_cursor")

    op.drop_index("ix_leadpage_inbox_ts", table_name="leadpage_inbox")
    op.drop_index("ix_leadpage_inbox_provider", table_name="leadpage_inbox")
    op.drop_index("ix_leadpage_inbox_signal_id", table_name="leadpage_inbox")
    op.drop_index("ix_leadpage_inbox_user_id", table_name="leadpage_inbox")
    op.drop_table("leadpage_inbox")

    op.drop_index("ix_leadpage_follows_provider", table_name="leadpage_follows")
    op.drop_index("ix_leadpage_follows_user_id", table_name="leadpage_follows")
    op.drop_table("leadpage_follows")

    op.drop_index("ix_leadpage_nonces_provider", table_name="leadpage_nonces")
    op.drop_table("leadpage_nonces")

    op.drop_index("ix_leadpage_signals_ts", table_name="leadpage_signals")
    op.drop_index("ix_leadpage_signals_provider", table_name="leadpage_signals")
    op.drop_table("leadpage_signals")

    op.drop_index("ix_leadpage_results_provider", table_name="leadpage_results")
    op.drop_table("leadpage_results")

    op.drop_index("ix_leadpage_provider_secrets_provider", table_name="leadpage_provider_secrets")
    op.drop_table("leadpage_provider_secrets")

    op.drop_index("ix_leadpage_providers_owner_user_id", table_name="leadpage_providers")
    op.drop_table("leadpage_providers")

    op.drop_index("ix_leadpage_users_email", table_name="leadpage_users")
    op.drop_table("leadpage_users")
