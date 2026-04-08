from datetime import datetime
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey,
    Integer, Numeric, String, Text, UniqueConstraint, ARRAY
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "admin_data"}

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)  # super_admin|admin|editor|viewer|trader
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    permissions = relationship("UserPermission", back_populates="user")
    refresh_tokens = relationship("RefreshToken", back_populates="user")


class Trader(Base):
    __tablename__ = "traders"
    __table_args__ = {"schema": "admin_data"}

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    default_lot_size = Column(Numeric(10, 2))
    linked_user_id = Column(Integer, ForeignKey("admin_data.users.id"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    linked_user = relationship("User", foreign_keys=[linked_user_id])


class Strategy(Base):
    __tablename__ = "strategies"
    __table_args__ = {"schema": "admin_data"}

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    magic_number = Column(BigInteger)
    symbol_filter = Column(ARRAY(String(30)), default=list)
    lot_size = Column(Numeric(10, 2))
    time_offset_min = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class UserPermission(Base):
    __tablename__ = "user_permissions"
    __table_args__ = (
        UniqueConstraint("user_id", "category_type", "category_id", name="uq_user_permission"),
        {"schema": "admin_data"},
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("admin_data.users.id"), nullable=False)
    category_type = Column(String(20), nullable=False)  # 'trader' | 'strategy'
    category_id = Column(Integer, nullable=False)
    permission = Column(String(20), nullable=False)     # 'view' | 'edit'

    user = relationship("User", back_populates="permissions")


class AttributionRule(Base):
    __tablename__ = "attribution_rules"
    __table_args__ = {"schema": "admin_data"}

    id = Column(Integer, primary_key=True)
    category_type = Column(String(20), nullable=False)
    category_id = Column(Integer, nullable=False)
    rule_type = Column(String(30), nullable=False)  # magic|comment_prefix|lot_size|symbol_list
    rule_value = Column(JSONB, nullable=False)
    priority = Column(Integer, default=100)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = {"schema": "admin_data"}

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("admin_data.users.id"), nullable=False)
    token_hash = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User", back_populates="refresh_tokens")


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "admin_data"}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("admin_data.users.id"))
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50))
    entity_id = Column(Integer)
    metadata = Column(JSONB)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class ExecutionControl(Base):
    """Singleton row (id=1): dashboard toggle for MT5 live order execution."""
    __tablename__ = "execution_control"
    __table_args__ = {"schema": "admin_data"}

    id = Column(Integer, primary_key=True)
    live_trading_enabled = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)
