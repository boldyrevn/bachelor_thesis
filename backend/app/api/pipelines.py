"""Pipeline API endpoints for CRUD operations and execution.

All operations use PipelineVersion model where each save creates a new version.
The pipeline_id in URL refers to the logical pipeline (groups versions).
"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.models.node_run import NodeRun
from app.models.pipeline_run import PipelineRun, PipelineRunResponse, RunStatus
from app.models.pipeline_version import (
    PipelineVersion,
    PipelineVersionCreate,
    PipelineVersionResponse,
    PipelineVersionUpdate,
    PipelineListItem,
)

router = APIRouter(prefix="/api/v1/pipelines", tags=["pipelines"])


@router.post(
    "", response_model=PipelineVersionResponse, status_code=status.HTTP_201_CREATED
)
async def create_pipeline(
    pipeline_data: PipelineVersionCreate,
    db: AsyncSession = Depends(get_db_session),
) -> PipelineVersion:
    """Create a new pipeline (version 1).

    Args:
        pipeline_data: Pipeline creation data
        db: Database session

    Returns:
        Created pipeline version

    Raises:
        HTTPException: If pipeline with same name exists
    """
    # Check for duplicate name in current versions
    result = await db.execute(
        select(PipelineVersion).where(
            PipelineVersion.name == pipeline_data.name,
            PipelineVersion.is_current == True,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pipeline with name '{pipeline_data.name}' already exists",
        )

    # Validate graph if provided
    if pipeline_data.graph_definition:
        from app.orchestration.graph_resolver import validate_pipeline_graph

        is_valid, error = validate_pipeline_graph(pipeline_data.graph_definition)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid graph definition: {error}",
            )

    # Generate a new logical pipeline_id
    pipeline_id = str(uuid.uuid4())

    # Create first version
    version = PipelineVersion(
        pipeline_id=pipeline_id,
        version=1,
        name=pipeline_data.name,
        description=pipeline_data.description,
        graph_definition=pipeline_data.graph_definition or {},
        is_current=True,
    )

    db.add(version)
    await db.commit()
    await db.refresh(version)

    return version


@router.get("", response_model=list[PipelineListItem])
async def list_pipelines(
    db: AsyncSession = Depends(get_db_session),
) -> list[PipelineListItem]:
    """List all pipelines (latest version of each).

    Args:
        db: Database session

    Returns:
        List of pipelines with their latest version info
    """
    # Get all current versions (one per pipeline_id)
    result = await db.execute(
        select(PipelineVersion)
        .where(PipelineVersion.is_current == True)
        .order_by(PipelineVersion.created_at.desc())
    )
    current_versions = result.scalars().all()

    return [
        PipelineListItem(
            pipeline_id=v.pipeline_id,
            name=v.name,
            description=v.description,
            latest_version=v.version,
            is_current_id=v.id,
            node_count=len(v.graph_definition.get("nodes", [])),
            edge_count=len(v.graph_definition.get("edges", [])),
            created_at=v.created_at,
            updated_at=v.updated_at,
        )
        for v in current_versions
    ]


@router.get("/{pipeline_id}", response_model=PipelineVersionResponse)
async def get_pipeline(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> PipelineVersion:
    """Get latest version of a pipeline.

    Args:
        pipeline_id: Logical pipeline UUID
        db: Database session

    Returns:
        Current pipeline version

    Raises:
        HTTPException: If pipeline not found
    """
    result = await db.execute(
        select(PipelineVersion).where(
            PipelineVersion.pipeline_id == pipeline_id,
            PipelineVersion.is_current == True,
        )
    )
    version = result.scalar_one_or_none()

    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline '{pipeline_id}' not found",
        )

    return version


@router.get("/{pipeline_id}/versions", response_model=list[PipelineVersionResponse])
async def list_pipeline_versions(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> list[PipelineVersion]:
    """List all versions of a pipeline.

    Args:
        pipeline_id: Logical pipeline UUID
        db: Database session

    Returns:
        List of pipeline versions ordered by version number
    """
    result = await db.execute(
        select(PipelineVersion)
        .where(PipelineVersion.pipeline_id == pipeline_id)
        .order_by(PipelineVersion.created_at.desc())
    )
    return list(result.scalars().all())


@router.get(
    "/{pipeline_id}/versions/{version_id}", response_model=PipelineVersionResponse
)
async def get_pipeline_version(
    pipeline_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> PipelineVersion:
    """Get a specific version of a pipeline.

    Args:
        pipeline_id: Logical pipeline UUID
        version_id: Pipeline version UUID
        db: Database session

    Returns:
        Specific pipeline version

    Raises:
        HTTPException: If pipeline or version not found
    """
    result = await db.execute(
        select(PipelineVersion).where(
            PipelineVersion.pipeline_id == pipeline_id,
            PipelineVersion.id == version_id,
        )
    )
    version = result.scalar_one_or_none()

    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version '{version_id}' not found in pipeline '{pipeline_id}'",
        )

    return version


@router.put("/{pipeline_id}", response_model=PipelineVersionResponse)
async def update_pipeline(
    pipeline_id: str,
    pipeline_data: PipelineVersionUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> PipelineVersion:
    """Update pipeline by creating a new version.

    Args:
        pipeline_id: Logical pipeline UUID
        pipeline_data: Update data
        db: Database session

    Returns:
        New pipeline version

    Raises:
        HTTPException: If pipeline not found or name conflict
    """
    # Get current version
    result = await db.execute(
        select(PipelineVersion).where(
            PipelineVersion.pipeline_id == pipeline_id,
            PipelineVersion.is_current == True,
        )
    )
    current = result.scalar_one_or_none()

    if not current:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline '{pipeline_id}' not found",
        )

    # Check name conflict if updating name
    new_name = pipeline_data.name or current.name
    if new_name != current.name:
        existing = await db.execute(
            select(PipelineVersion).where(
                PipelineVersion.name == new_name,
                PipelineVersion.is_current == True,
                PipelineVersion.pipeline_id != pipeline_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Pipeline with name '{new_name}' already exists",
            )

    # Validate graph if updating
    new_graph = pipeline_data.graph_definition or current.graph_definition
    if pipeline_data.graph_definition is not None:
        from app.orchestration.graph_resolver import validate_pipeline_graph

        is_valid, error = validate_pipeline_graph(pipeline_data.graph_definition)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid graph definition: {error}",
            )

    # Mark current version as not current
    current.is_current = False

    # Create new version
    new_version = PipelineVersion(
        pipeline_id=pipeline_id,
        version=current.version + 1,
        name=new_name,
        description=(
            pipeline_data.description
            if pipeline_data.description is not None
            else current.description
        ),
        graph_definition=new_graph,
        is_current=True,
    )

    db.add(new_version)
    await db.commit()
    await db.refresh(new_version)

    return new_version


@router.delete("/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete pipeline and all its versions.

    Args:
        pipeline_id: Logical pipeline UUID
        db: Database session

    Raises:
        HTTPException: If pipeline not found
    """
    result = await db.execute(
        select(PipelineVersion).where(
            PipelineVersion.pipeline_id == pipeline_id,
            PipelineVersion.is_current == True,
        )
    )
    current = result.scalar_one_or_none()

    if not current:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline '{pipeline_id}' not found",
        )

    # Delete all versions (cascade handles this)
    result = await db.execute(
        select(PipelineVersion).where(PipelineVersion.pipeline_id == pipeline_id)
    )
    versions = result.scalars().all()
    for v in versions:
        await db.delete(v)
    await db.commit()


@router.post(
    "/{pipeline_id}/run",
    response_model=PipelineRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def run_pipeline(
    pipeline_id: str,
    parameters: dict[str, Any] | None = None,
    db: AsyncSession = Depends(get_db_session),
) -> PipelineRun:
    """Run a pipeline asynchronously via the PipelineRunner background scheduler.

    Creates a PipelineRun record with status RUNNING and NodeRun records
    for every node in the graph (status PENDING). The PipelineRunner
    polls the DB and picks up ready nodes automatically.

    Args:
        pipeline_id: Logical pipeline UUID
        parameters: Pipeline input parameters
        db: Database session

    Returns:
        Created pipeline run (status will be RUNNING)

    Raises:
        HTTPException: If pipeline not found
    """
    # Get current version
    result = await db.execute(
        select(PipelineVersion).where(
            PipelineVersion.pipeline_id == pipeline_id,
            PipelineVersion.is_current == True,
        )
    )
    version = result.scalar_one_or_none()

    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline '{pipeline_id}' not found",
        )

    graph = version.graph_definition
    nodes = graph.get("nodes", [])

    if not nodes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pipeline has no nodes",
        )

    # Create pipeline run
    run_id = str(uuid.uuid4())
    pipeline_run = PipelineRun(
        id=run_id,
        version_id=version.id,
        status=RunStatus.RUNNING,
        parameters=parameters or {},
        started_at=datetime.utcnow(),
    )
    db.add(pipeline_run)

    # Create NodeRun records for every node (status PENDING)
    for node in nodes:
        node_id = node.get("id")
        node_type = node.get("data", {}).get("nodeType") or node.get("data", {}).get(
            "node_type"
        )
        if not node_id or not node_type:
            continue

        node_run = NodeRun(
            pipeline_run_id=run_id,
            node_id=node_id,
            node_type=node_type,
            status=RunStatus.PENDING,
        )
        db.add(node_run)

    await db.commit()
    await db.refresh(pipeline_run)

    return pipeline_run


@router.get("/runs/{run_id}", response_model=PipelineRunResponse)
async def get_pipeline_run(
    run_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> PipelineRun:
    """Get pipeline run by ID.

    Args:
        run_id: Pipeline run UUID
        db: Database session

    Returns:
        Pipeline run

    Raises:
        HTTPException: If run not found
    """
    result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    pipeline_run = result.scalar_one_or_none()

    if not pipeline_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline run '{run_id}' not found",
        )

    return pipeline_run


pipelines_router = router
