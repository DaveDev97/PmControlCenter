"""Async SQLAlchemy engine, session and declarative base.

The desktop edition keeps everything in a **shared in-memory SQLite database**.
Data is rebuilt from the Excel source files on startup and on every refresh, so
nothing is ever persisted to disk. A ``StaticPool`` with a single underlying
connection is required: the default pool would give each connection its own
private in-memory database, and the loaded tables would appear empty to
subsequent requests.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async DB session."""
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create all tables (idempotent)."""
    # Import models so they are registered on the metadata before create_all.
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def reset_db() -> None:
    """Drop and recreate all tables (used before reloading Excel data)."""
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
