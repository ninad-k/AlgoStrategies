"""execution_control for MT5 live trading toggle

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "execution_control",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("live_trading_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="admin_data",
    )
    op.execute(
        """
        INSERT INTO admin_data.execution_control (id, live_trading_enabled)
        VALUES (1, false)
        ON CONFLICT (id) DO NOTHING
        """
    )


def downgrade():
    op.drop_table("execution_control", schema="admin_data")
