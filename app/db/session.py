from __future__ import annotations

import asyncio
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.db.models import Base

# Synchronous SQLAlchemy engine and session
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency to provide a DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def init_db() -> None:
    """Initialize database schema in development.

    Runs create_all in a thread to avoid blocking the event loop.
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, Base.metadata.create_all, engine)
    # Lightweight migration for SQLite to add new columns if missing
    if engine.dialect.name == "sqlite":
        def _migrate_sqlite() -> None:
            with engine.begin() as conn:
                try:
                    cols = conn.exec_driver_sql("PRAGMA table_info(kb_entries)").fetchall()
                    names = {c[1] for c in cols}
                    if "embedding" not in names:
                        conn.exec_driver_sql("ALTER TABLE kb_entries ADD COLUMN embedding JSON")
                except Exception:
                    pass
        await loop.run_in_executor(None, _migrate_sqlite)
