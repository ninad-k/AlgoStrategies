"""
Intelligence Suite — Audit Logger SQLAlchemy Schema
======================================================
Defines ORM models for audit entries and reconciliation results.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class AuditEntry(Base):
    """Immutable record of every trade event, AI decision, and risk check."""

    __tablename__ = "audit_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    symbol = Column(String(20), nullable=True, index=True)
    action = Column(String(10), nullable=True)
    details_json = Column(Text, nullable=True)
    model_name = Column(String(50), nullable=True)
    confidence = Column(Float, nullable=True)
    profit = Column(Float, nullable=True)
    ai_reasoning = Column(Text, nullable=True)
    indicators_json = Column(Text, nullable=True)
    risk_allowed = Column(String(10), nullable=True)
    risk_reason = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<AuditEntry(id={self.id}, ts={self.timestamp}, "
            f"type={self.event_type}, symbol={self.symbol})>"
        )


class ReconciliationResult(Base):
    """Stores backtest-vs-live reconciliation snapshots."""

    __tablename__ = "reconciliation_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    backtest_pnl = Column(Float, nullable=False)
    live_pnl = Column(Float, nullable=False)
    deviation = Column(Float, nullable=False)
    match_rate = Column(Float, nullable=False)
    total_backtest_trades = Column(Integer, nullable=True)
    total_live_trades = Column(Integer, nullable=True)
    details_json = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<ReconciliationResult(id={self.id}, ts={self.timestamp}, "
            f"match_rate={self.match_rate:.2%})>"
        )


def get_engine(db_path: str = "logs/audit_logger.db"):
    """Create a SQLAlchemy engine for the audit database."""
    return create_engine(f"sqlite:///{db_path}", echo=False)


def create_tables(db_path: str = "logs/audit_logger.db") -> sessionmaker:
    """Create all tables and return a session factory."""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
