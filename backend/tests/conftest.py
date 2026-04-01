"""Pytest fixtures and configuration for FlowForge tests."""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app.main import app
from app.models.base import Base


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    """Create PostgreSQL container for integration tests."""
    with PostgresContainer("postgres:14-alpine", driver="asyncpg") as postgres:
        yield postgres


@pytest.fixture
async def db_session(
    postgres_container: PostgresContainer,
) -> AsyncGenerator[AsyncSession, None]:
    """Create async database session for tests using testcontainers PostgreSQL."""
    db_url = postgres_container.get_connection_url()
    # Replace postgres:// with postgresql+asyncpg://
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(
        db_url,
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for testing API endpoints."""

    # Override the database session dependency
    async def override_get_db_session():
        yield db_session

    from app.api import dependencies
    from fastapi.testclient import TestClient

    # Create app with overridden dependency
    from app.main import create_app

    test_app = create_app()
    test_app.dependency_overrides[dependencies.get_db_session] = override_get_db_session

    try:
        async with AsyncClient(
            transport=ASGITransport(app=test_app),
            base_url="http://test",
        ) as ac:
            yield ac
    finally:
        # Clear overrides
        test_app.dependency_overrides.clear()


@pytest.fixture
def sample_pipeline_data() -> dict:
    """Sample pipeline graph definition for testing."""
    return {
        "nodes": [
            {
                "id": "params-1",
                "type": "PipelineParams",
                "position": {"x": 100, "y": 100},
                "data": {
                    "parameters": [
                        {"name": "date", "type": "string", "default": "2024-01-01"},
                        {"name": "env", "type": "string", "default": "dev"},
                    ]
                },
            },
            {
                "id": "extract-1",
                "type": "PostgresToS3",
                "position": {"x": 300, "y": 100},
                "data": {
                    "connection_id": "pg-conn-1",
                    "query": "SELECT * FROM users",
                    "s3_path": "s3://warehouse/users/{{ date }}",
                },
            },
        ],
        "edges": [
            {
                "id": "edge-1",
                "source": "params-1",
                "target": "extract-1",
            }
        ],
    }
