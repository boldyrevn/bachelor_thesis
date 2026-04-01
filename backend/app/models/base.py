"""SQLAlchemy async base model and session factory."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all SQLAlchemy models with async support."""

    pass


def create_async_sessionmaker(database_url: str) -> async_sessionmaker:
    """Create async sessionmaker for database connections.

    Args:
        database_url: SQLAlchemy database URL (e.g., postgresql+asyncpg://...)

    Returns:
        Async sessionmaker instance
    """
    engine = create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )
    return async_sessionmaker(bind=engine, expire_on_commit=False)


class TimestampMixin:
    """Mixin adding created_at and updated_at timestamps to models."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
