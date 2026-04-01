"""API dependencies."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency."""
    from app.main import db_session_factory

    if db_session_factory is None:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    async with db_session_factory() as session:
        yield session
