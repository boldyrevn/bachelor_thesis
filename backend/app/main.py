"""FastAPI application entry point."""

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.api.connections import connections_router
from app.api.demo import demo_router
from app.api.pipelines import pipelines_router
from app.core.config import settings, setup_logging
from app.models.base import Base


# Global database session factory and engine
db_session_factory: async_sessionmaker | None = None
db_engine: AsyncEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    global db_session_factory, db_engine

    # Startup
    setup_logging(debug=settings.DEBUG)

    # Create engine and session factory
    db_engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
    db_session_factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)

    # Create all tables (for development - use Alembic migrations in production)
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Export OpenAPI spec to file
    openapi_spec = app.openapi()
    openapi_path = Path(__file__).parent.parent / "openapi.json"
    with open(openapi_path, "w") as f:
        json.dump(openapi_spec, f, indent=2)

    yield

    # Shutdown
    if db_engine:
        await db_engine.dispose()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="FlowForge - Low-code оркестратор данных с типизированными артефактами",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @app.get("/health")
    async def health_check() -> dict:
        return {"status": "healthy", "service": settings.APP_NAME}

    # Include routers
    app.include_router(demo_router)
    app.include_router(connections_router)
    app.include_router(pipelines_router)

    return app


app = create_app()
