"""Connection API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connections.service import test_connection
from app.models.connection import Connection, ConnectionType
from app.schemas.connection import (
    CONNECTION_CLASSES,
    get_connection_class,
)

from .dependencies import get_db_session

logger = logging.getLogger(__name__)

connections_router = APIRouter(prefix="/api/v1/connections", tags=["connections"])


class ConnectionCreateRequest(BaseModel):
    """Request model for creating a connection."""

    name: str
    connection_type: ConnectionType
    config: dict[str, Any]
    secrets: dict[str, Any]
    description: str | None = None


class ConnectionUpdateRequest(BaseModel):
    """Request model for updating a connection."""

    name: str | None = None
    config: dict[str, Any] | None = None
    secrets: dict[str, Any] | None = None
    description: str | None = None


class ConnectionTypeInfo(BaseModel):
    """Connection type metadata for frontend form generation."""

    type: str
    title: str
    json_schema: dict[str, Any] = Field(alias="schema")


async def get_connection_or_404(
    connection_id: str, session: AsyncSession = Depends(get_db_session)
) -> Connection:
    """Get connection by ID or raise 404."""
    import uuid

    try:
        uuid.UUID(connection_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection with id '{connection_id}' not found",
        )

    result = await session.execute(
        select(Connection).where(Connection.id == connection_id)
    )
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection with id '{connection_id}' not found",
        )

    return connection


def _validate_and_split(
    connection_type: str, config: dict[str, Any], secrets: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate connection via typed class and split for DB storage.

    Returns:
        (config_dict, secrets_dict) ready for DB storage
    """
    conn_cls = get_connection_class(connection_type)
    merged = {**config, **secrets}
    instance = conn_cls(**merged)
    return instance.split_for_db()


@connections_router.get(
    "/types",
    response_model=list[ConnectionTypeInfo],
    summary="List available connection types with schemas",
)
async def list_connection_types() -> list[ConnectionTypeInfo]:
    """Return metadata for all connection types for frontend form generation."""
    titles = {
        "postgres": "PostgreSQL",
        "clickhouse": "ClickHouse",
        "s3": "S3 / MinIO",
        "spark": "Apache Spark",
    }
    return [
        ConnectionTypeInfo(
            type=conn_type,
            title=titles.get(conn_type, conn_type),
            schema=conn_cls.model_json_schema(),
        )
        for conn_type, conn_cls in CONNECTION_CLASSES.items()
    ]


@connections_router.post(
    "",
    response_model=dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new connection",
)
async def create_connection(
    request: ConnectionCreateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Create a new connection."""
    validated_config, validated_secrets = _validate_and_split(
        request.connection_type.value, request.config, request.secrets
    )

    result = await session.execute(
        select(Connection).where(Connection.name == request.name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Connection with name '{request.name}' already exists",
        )

    connection = Connection(
        name=request.name,
        connection_type=request.connection_type,
        config=validated_config,
        secrets=validated_secrets,
        description=request.description,
    )

    session.add(connection)
    await session.commit()
    await session.refresh(connection)

    logger.info(f"Created connection: {connection.id} ({connection.name})")

    return {
        "id": connection.id,
        "name": connection.name,
        "connection_type": connection.connection_type.value,
        "message": "Connection created successfully",
    }


@connections_router.get(
    "",
    response_model=list[dict[str, Any]],
    summary="List all connections",
)
async def list_connections(
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """Get list of all connections (without secrets)."""
    result = await session.execute(
        select(Connection).order_by(Connection.created_at.desc())
    )
    connections = result.scalars().all()

    return [
        {
            "id": conn.id,
            "name": conn.name,
            "connection_type": conn.connection_type.value,
            "config": conn.config,
            "description": conn.description,
            "created_at": conn.created_at.isoformat(),
            "updated_at": conn.updated_at.isoformat(),
        }
        for conn in connections
    ]


@connections_router.get(
    "/{connection_id}",
    response_model=dict[str, Any],
    summary="Get connection by ID",
)
async def get_connection(
    connection: Connection = Depends(get_connection_or_404),
) -> dict[str, Any]:
    """Get connection details by ID (without secrets)."""
    return {
        "id": connection.id,
        "name": connection.name,
        "connection_type": connection.connection_type.value,
        "config": connection.config,
        "description": connection.description,
        "created_at": connection.created_at.isoformat(),
        "updated_at": connection.updated_at.isoformat(),
    }


@connections_router.put(
    "/{connection_id}",
    response_model=dict[str, Any],
    summary="Update connection",
)
async def update_connection(
    connection_id: str,
    request: ConnectionUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Update an existing connection."""
    connection = await get_connection_or_404(connection_id, session)

    if request.name and request.name != connection.name:
        result = await session.execute(
            select(Connection).where(Connection.name == request.name)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Connection with name '{request.name}' already exists",
            )
        connection.name = request.name

    if request.config is not None or request.secrets is not None:
        current_config = connection.config if request.config is None else request.config
        current_secrets = (
            connection.secrets if request.secrets is None else request.secrets
        )
        try:
            validated_config, validated_secrets = _validate_and_split(
                connection.connection_type.value, current_config, current_secrets
            )
            connection.config = validated_config
            connection.secrets = validated_secrets
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation error: {str(e)}",
            )

    if request.description is not None:
        connection.description = request.description

    await session.commit()
    await session.refresh(connection)

    logger.info(f"Updated connection: {connection.id} ({connection.name})")

    return {
        "id": connection.id,
        "name": connection.name,
        "message": "Connection updated successfully",
    }


@connections_router.delete(
    "/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete connection",
)
async def delete_connection(
    connection: Connection = Depends(get_connection_or_404),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a connection."""
    await session.delete(connection)
    await session.commit()

    logger.info(f"Deleted connection: {connection.id} ({connection.name})")


@connections_router.post(
    "/{connection_id}/test",
    response_model=dict[str, Any],
    summary="Test connection",
)
async def test_connection_endpoint(
    connection: Connection = Depends(get_connection_or_404),
) -> dict[str, Any]:
    """Test a connection to verify it works."""
    result = await test_connection(
        connection.connection_type.value,
        connection.config,
        connection.secrets,
    )

    logger.info(
        f"Tested connection: {connection.id} ({connection.name}) - {'Success' if result.success else 'Failed'}"
    )

    return result.to_dict()
