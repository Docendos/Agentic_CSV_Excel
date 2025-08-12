from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from ..settings import settings

logger = logging.getLogger("ai-df-chat.db")


class Base(DeclarativeBase):
    """Declarative base for SQLAlchemy models."""
    pass


_engine: AsyncEngine | None = None
_SessionMaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """
    Build a single global async engine.
    Expect settings.database_url like: postgresql+asyncpg://user:pass@host:5432/db
    """
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_recycle=1800,   # recycle stale connections
            future=True,
            # connect_args={}  # add {"ssl": True} if you need SSL
        )
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    global _SessionMaker
    if _SessionMaker is None:
        _SessionMaker = async_sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionMaker


async def init_models(retries: int = 20, delay: float = 1.5) -> None:
    """
    Robust startup: wait for DB to be ready, then create tables.
    Retries handle cases where Postgres is booting or transiently dropping connections.
    """
    engine = get_engine()
    from .models import ChatQA
    
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
                await conn.run_sync(Base.metadata.create_all)

            logger.info("✅ Database is ready (tables ensured).")
            return
        except Exception as e:
            last_exc = e
            logger.warning(f"DB init attempt {attempt}/{retries} failed: {e!r}")
            await asyncio.sleep(delay)

    raise last_exc if last_exc else RuntimeError("Database initialization failed")


async def dispose_engine() -> None:
    eng = get_engine()
    await eng.dispose()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency: yields an async session per request.
    """
    Session = get_session_maker()
    async with Session() as session:
        yield session
