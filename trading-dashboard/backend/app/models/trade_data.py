import uuid
from datetime import datetime
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey,
    Integer, Numeric, SmallInteger, String, Text, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = {"schema": "trade_data"}

    id = Column(Integer, primary_key=True)
    account_id = Column(String(50), unique=True, nullable=False)
    broker = Column(String(100))
    currency = Column(String(10), default="USD")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    trades = relationship("Trade", back_populates="account", foreign_keys="Trade.account_id")


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = (
        UniqueConstraint("account_id", "ticket", name="uq_account_ticket"),
        {"schema": "trade_data"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    account_id = Column(String(50), ForeignKey("trade_data.accounts.account_id"), nullable=False)
    ticket = Column(BigInteger, nullable=False)
    open_time = Column(DateTime(timezone=True), nullable=False)
    close_time = Column(DateTime(timezone=True))
    symbol = Column(String(30), nullable=False)
    type = Column(String(10), nullable=False)
    lots = Column(Numeric(10, 2), nullable=False)
    open_price = Column(Numeric(16, 6), nullable=False)
    close_price = Column(Numeric(16, 6))
    sl = Column(Numeric(16, 6))
    tp = Column(Numeric(16, 6))
    profit = Column(Numeric(14, 4))
    commission = Column(Numeric(14, 4), default=0)
    swap = Column(Numeric(14, 4), default=0)
    comment = Column(Text)
    magic = Column(BigInteger)
    upload_batch_id = Column(UUID(as_uuid=True), nullable=False)

    account = relationship("Account", back_populates="trades", foreign_keys=[account_id])
    attributions = relationship("TradeAttribution", back_populates="trade")
    risk_metrics = relationship("RiskMetrics", back_populates="trade", uselist=False)

    @property
    def net_profit(self):
        return (self.profit or 0) + (self.commission or 0) + (self.swap or 0)


class TradeAttribution(Base):
    __tablename__ = "trade_attributions"
    __table_args__ = {"schema": "trade_data"}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trade_id = Column(BigInteger, ForeignKey("trade_data.trades.id"), nullable=False)
    category_type = Column(String(20), nullable=False)  # 'trader' | 'strategy' | 'guest'
    category_id = Column(Integer)                        # NULL for guest
    attribution_level = Column(SmallInteger, nullable=False)
    confidence = Column(Numeric(5, 4), default=1.0)
    is_primary = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    trade = relationship("Trade", back_populates="attributions")


class RiskMetrics(Base):
    __tablename__ = "risk_metrics"
    __table_args__ = {"schema": "trade_data"}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trade_id = Column(BigInteger, ForeignKey("trade_data.trades.id"), unique=True, nullable=False)
    has_sl = Column(Boolean, nullable=False)
    has_tp = Column(Boolean, nullable=False)
    planned_rr = Column(Numeric(10, 4))
    realised_rr = Column(Numeric(10, 4))
    rr_deviation = Column(Numeric(10, 4))
    risk_pips = Column(Numeric(10, 4))
    reward_pips = Column(Numeric(10, 4))

    trade = relationship("Trade", back_populates="risk_metrics")
