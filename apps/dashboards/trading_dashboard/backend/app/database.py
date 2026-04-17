from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schemas():
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS trade_data"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS admin_data"))
        conn.commit()
