"""FastAPI application entry point."""

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.api.connections import connections_router
from app.api.demo import demo_router
from app.api.node_types import node_types_router
from app.api.pipeline_runs import pipeline_runs_router, global_runs_router
from app.api.pipelines import pipelines_router
from app.core.config import settings
from app.core.logging_setup import setup_server_logging
from app.models.base import Base
from app.orchestration.runner import get_runner

logger = logging.getLogger(__name__)


# Global database session factory and engine
db_session_factory: async_sessionmaker | None = None
db_engine: AsyncEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    global db_session_factory, db_engine

    # Startup
    setup_server_logging(log_dir=settings.LOG_DIR, level=logging.DEBUG if settings.DEBUG else logging.INFO)

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

    # Scan and persist node types on startup
    from app.nodes.registry import NodeRegistry
    from app.nodes.scanner import NodeScanner

    # Scan and import all node modules
    NodeRegistry.scan_nodes()

    # Persist node metadata to DB
    async_session = async_sessionmaker(bind=db_engine, expire_on_commit=False)
    async with async_session() as session:
        scanner = NodeScanner(session)
        try:
            stats = await scanner.scan_and_persist()
            if stats["errors"]:
                logger.warning(
                    f"Node scan completed with {len(stats['errors'])} errors: {stats['errors']}"
                )
            else:
                logger.info(
                    f"Node scan completed: {stats['total']} node types registered"
                )
        except Exception as e:
            logger.error(f"Failed to scan node types on startup: {e}", exc_info=True)

    # Export OpenAPI spec to file
    openapi_spec = app.openapi()
    openapi_path = Path(__file__).parent.parent / "openapi.json"
    with open(openapi_path, "w") as f:
        json.dump(openapi_spec, f, indent=2)

    # Start PipelineRunner background scheduler
    runner = get_runner()
    await runner.start()
    logger.info("PipelineRunner started (background scheduler)")

    yield

    # Shutdown
    runner = get_runner()
    await runner.stop()
    logger.info("PipelineRunner stopped")

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
    app.include_router(node_types_router)
    # Global runs endpoint MUST be registered before pipelines_router
    # to avoid /api/v1/pipelines/runs being caught by /{pipeline_id} routes
    app.include_router(global_runs_router)
    app.include_router(pipelines_router)
    app.include_router(pipeline_runs_router)

    return app


app = create_app()
