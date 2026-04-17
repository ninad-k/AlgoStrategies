"""init schemas and tables

Revision ID: 0001
Revises:
Create Date: 2026-04-06
"""
import os
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from passlib.context import CryptContext

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def upgrade():
    # ── Schemas ──────────────────────────────────────────────────────────────
    op.execute("CREATE SCHEMA IF NOT EXISTS trade_data")
    op.execute("CREATE SCHEMA IF NOT EXISTS admin_data")

    # ── trade_data.accounts ───────────────────────────────────────────────────
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("account_id", sa.String(50), unique=True, nullable=False),
        sa.Column("broker", sa.String(100)),
        sa.Column("currency", sa.String(10), server_default="USD"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="trade_data",
    )

    # ── trade_data.trades ─────────────────────────────────────────────────────
    op.create_table(
        "trades",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.String(50), sa.ForeignKey("trade_data.accounts.account_id"), nullable=False),
        sa.Column("ticket", sa.BigInteger, nullable=False),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close_time", sa.DateTime(timezone=True)),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("lots", sa.Numeric(10, 2), nullable=False),
        sa.Column("open_price", sa.Numeric(16, 6), nullable=False),
        sa.Column("close_price", sa.Numeric(16, 6)),
        sa.Column("sl", sa.Numeric(16, 6)),
        sa.Column("tp", sa.Numeric(16, 6)),
        sa.Column("profit", sa.Numeric(14, 4)),
        sa.Column("commission", sa.Numeric(14, 4), server_default="0"),
        sa.Column("swap", sa.Numeric(14, 4), server_default="0"),
        sa.Column("comment", sa.Text),
        sa.Column("magic", sa.BigInteger),
        sa.Column("upload_batch_id", UUID(as_uuid=True), nullable=False),
        sa.UniqueConstraint("account_id", "ticket", name="uq_account_ticket"),
        schema="trade_data",
    )

    # ── trade_data.trade_attributions ─────────────────────────────────────────
    op.create_table(
        "trade_attributions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("trade_id", sa.BigInteger, sa.ForeignKey("trade_data.trades.id"), nullable=False),
        sa.Column("category_type", sa.String(20), nullable=False),
        sa.Column("category_id", sa.Integer),
        sa.Column("attribution_level", sa.SmallInteger, nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), server_default="1.0"),
        sa.Column("is_primary", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="trade_data",
    )

    # ── trade_data.risk_metrics ───────────────────────────────────────────────
    op.create_table(
        "risk_metrics",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("trade_id", sa.BigInteger, sa.ForeignKey("trade_data.trades.id"), unique=True, nullable=False),
        sa.Column("has_sl", sa.Boolean, nullable=False),
        sa.Column("has_tp", sa.Boolean, nullable=False),
        sa.Column("planned_rr", sa.Numeric(10, 4)),
        sa.Column("realised_rr", sa.Numeric(10, 4)),
        sa.Column("rr_deviation", sa.Numeric(10, 4)),
        sa.Column("risk_pips", sa.Numeric(10, 4)),
        sa.Column("reward_pips", sa.Numeric(10, 4)),
        schema="trade_data",
    )

    # ── admin_data.users ──────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="admin_data",
    )

    # ── admin_data.traders ────────────────────────────────────────────────────
    op.create_table(
        "traders",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("default_lot_size", sa.Numeric(10, 2)),
        sa.Column("linked_user_id", sa.Integer, sa.ForeignKey("admin_data.users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="admin_data",
    )

    # ── admin_data.strategies ─────────────────────────────────────────────────
    op.create_table(
        "strategies",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("magic_number", sa.BigInteger),
        sa.Column("symbol_filter", ARRAY(sa.String(30)), server_default="{}"),
        sa.Column("lot_size", sa.Numeric(10, 2)),
        sa.Column("time_offset_min", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="admin_data",
    )

    # ── admin_data.user_permissions ───────────────────────────────────────────
    op.create_table(
        "user_permissions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("admin_data.users.id"), nullable=False),
        sa.Column("category_type", sa.String(20), nullable=False),
        sa.Column("category_id", sa.Integer, nullable=False),
        sa.Column("permission", sa.String(20), nullable=False),
        sa.UniqueConstraint("user_id", "category_type", "category_id", name="uq_user_permission"),
        schema="admin_data",
    )

    # ── admin_data.attribution_rules ──────────────────────────────────────────
    op.create_table(
        "attribution_rules",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("category_type", sa.String(20), nullable=False),
        sa.Column("category_id", sa.Integer, nullable=False),
        sa.Column("rule_type", sa.String(30), nullable=False),
        sa.Column("rule_value", JSONB, nullable=False),
        sa.Column("priority", sa.Integer, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="admin_data",
    )

    # ── admin_data.refresh_tokens ─────────────────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("admin_data.users.id"), nullable=False),
        sa.Column("token_hash", sa.String(255), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="admin_data",
    )

    # ── admin_data.audit_log ──────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("admin_data.users.id")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50)),
        sa.Column("entity_id", sa.Integer),
        sa.Column("metadata", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="admin_data",
    )

    # ── Seed: Guest trader ────────────────────────────────────────────────────
    op.execute("""
        INSERT INTO admin_data.traders (id, name)
        VALUES (0, 'Guest/Common')
        ON CONFLICT DO NOTHING
    """)

    # ── Seed: Super Admin ─────────────────────────────────────────────────────
    email = os.environ.get("SUPER_ADMIN_EMAIL", "admin@reycapital.com")
    raw_password = os.environ.get("SUPER_ADMIN_PASSWORD", "changeme123")
    hashed = pwd_context.hash(raw_password)
    op.execute(f"""
        INSERT INTO admin_data.users (email, hashed_password, role)
        VALUES ('{email}', '{hashed}', 'super_admin')
        ON CONFLICT (email) DO NOTHING
    """)


def downgrade():
    for tbl in ["audit_log", "refresh_tokens", "attribution_rules",
                "user_permissions", "strategies", "traders", "users"]:
        op.drop_table(tbl, schema="admin_data")
    for tbl in ["risk_metrics", "trade_attributions", "trades", "accounts"]:
        op.drop_table(tbl, schema="trade_data")
    op.execute("DROP SCHEMA IF EXISTS admin_data CASCADE")
    op.execute("DROP SCHEMA IF EXISTS trade_data CASCADE")
