"""Node types API endpoints for discovering and managing node metadata."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.node_type import NodeType, NodeTypeListResponse, NodeTypeResponse
from app.nodes.registry import NodeRegistry
from app.nodes.scanner import NodeScanner, NodeScannerError

from .dependencies import get_db_session

logger = logging.getLogger(__name__)

node_types_router = APIRouter(prefix="/api/v1/node-types", tags=["node-types"])


@node_types_router.get(
    "",
    response_model=NodeTypeListResponse,
    summary="List all node types",
    description="Retrieve all available node types with their schemas and metadata.",
)
async def list_node_types(
    db_session: AsyncSession = Depends(get_db_session),
) -> NodeTypeListResponse:
    """List all node types with their input/output schemas.

    Returns metadata for all node types available in the system,
    including titles, descriptions, categories, and JSON schemas
    for frontend form generation.

    Returns:
        NodeTypeListResponse with list of node types and total count
    """
    result = await db_session.execute(
        select(NodeType).where(NodeType.is_active == True).order_by(NodeType.title)
    )
    node_types = result.scalars().all()

    return NodeTypeListResponse(
        node_types=[NodeTypeResponse.model_validate(nt) for nt in node_types],
        total=len(node_types),
    )


@node_types_router.get(
    "/{node_type}",
    response_model=NodeTypeResponse,
    summary="Get node type by ID",
    description="Retrieve metadata for a specific node type.",
)
async def get_node_type(
    node_type: str,
    db_session: AsyncSession = Depends(get_db_session),
) -> NodeTypeResponse:
    """Get a specific node type by its identifier.

    Args:
        node_type: Node type identifier (e.g., 'text_output', 'spark_transform')

    Returns:
        NodeTypeResponse with node metadata

    Raises:
        HTTPException 404: If node type not found
    """
    node = await db_session.get(NodeType, node_type)
    if not node or not node.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node type '{node_type}' not found",
        )

    return NodeTypeResponse.model_validate(node)


@node_types_router.post(
    "/scan",
    response_model=dict,
    summary="Scan and sync node types",
    description="Rescan node modules and synchronize metadata with the database.",
)
async def scan_node_types(
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Scan node modules and synchronize metadata to the database.

    This endpoint:
    1. Scans the app.nodes package for all registered node types
    2. Extracts metadata (title, description, category, schemas)
    3. Upserts into the node_types table (create or update)
    4. Deactivates node types that are no longer registered in code

    Returns:
        Dictionary with scan statistics (created, updated, deactivated, total, errors)

    Raises:
        HTTPException 500: If scan operation fails
    """
    try:
        scanner = NodeScanner(db_session)
        stats = await scanner.scan_and_persist()

        if stats["errors"]:
            logger.warning(f"Node scan completed with {len(stats['errors'])} errors")

        return stats

    except NodeScannerError as e:
        logger.error(f"Node scan failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    except Exception as e:
        logger.error(f"Unexpected error during node scan: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during node scan",
        )
