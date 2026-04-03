"""Pipeline API endpoints for CRUD operations and execution."""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.models.pipeline import (
    Pipeline,
    PipelineCreate,
    PipelineResponse,
    PipelineUpdate,
)
from app.models.pipeline_run import PipelineRun, PipelineRunResponse, RunStatus
from app.orchestration.pipeline_executor import execute_pipeline_with_streaming

router = APIRouter(prefix="/api/v1/pipelines", tags=["pipelines"])


@router.post("", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline(
    pipeline_data: PipelineCreate,
    db: AsyncSession = Depends(get_db_session),
) -> Pipeline:
    """Create a new pipeline.

    Args:
        pipeline_data: Pipeline creation data
        db: Database session

    Returns:
        Created pipeline

    Raises:
        HTTPException: If pipeline with same name exists
    """
    # Check for duplicate name
    result = await db.execute(
        select(Pipeline).where(Pipeline.name == pipeline_data.name)
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

    # Create pipeline
    pipeline = Pipeline(
        name=pipeline_data.name,
        description=pipeline_data.description,
        graph_definition=pipeline_data.graph_definition or {},
    )

    db.add(pipeline)
    await db.commit()
    await db.refresh(pipeline)

    return pipeline


@router.get("", response_model=list[PipelineResponse])
async def list_pipelines(
    db: AsyncSession = Depends(get_db_session),
) -> list[Pipeline]:
    """List all pipelines.

    Args:
        db: Database session

    Returns:
        List of pipelines
    """
    result = await db.execute(select(Pipeline).order_by(Pipeline.created_at.desc()))
    return list(result.scalars().all())


@router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> Pipeline:
    """Get pipeline by ID.

    Args:
        pipeline_id: Pipeline UUID
        db: Database session

    Returns:
        Pipeline

    Raises:
        HTTPException: If pipeline not found
    """
    result = await db.execute(select(Pipeline).where(Pipeline.id == pipeline_id))
    pipeline = result.scalar_one_or_none()

    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline '{pipeline_id}' not found",
        )

    return pipeline


@router.put("/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(
    pipeline_id: str,
    pipeline_data: PipelineUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> Pipeline:
    """Update pipeline.

    Args:
        pipeline_id: Pipeline UUID
        pipeline_data: Update data
        db: Database session

    Returns:
        Updated pipeline

    Raises:
        HTTPException: If pipeline not found or name conflict
    """
    result = await db.execute(select(Pipeline).where(Pipeline.id == pipeline_id))
    pipeline = result.scalar_one_or_none()

    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline '{pipeline_id}' not found",
        )

    # Check name conflict if updating name
    if pipeline_data.name and pipeline_data.name != pipeline.name:
        existing = await db.execute(
            select(Pipeline).where(
                Pipeline.name == pipeline_data.name, Pipeline.id != pipeline_id
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Pipeline with name '{pipeline_data.name}' already exists",
            )
        pipeline.name = pipeline_data.name

    # Validate graph if updating
    if pipeline_data.graph_definition:
        from app.orchestration.graph_resolver import validate_pipeline_graph

        is_valid, error = validate_pipeline_graph(pipeline_data.graph_definition)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid graph definition: {error}",
            )
        pipeline.graph_definition = pipeline_data.graph_definition

    if pipeline_data.description is not None:
        pipeline.description = pipeline_data.description

    pipeline.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(pipeline)

    return pipeline


@router.delete("/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete pipeline.

    Args:
        pipeline_id: Pipeline UUID
        db: Database session

    Raises:
        HTTPException: If pipeline not found
    """
    result = await db.execute(select(Pipeline).where(Pipeline.id == pipeline_id))
    pipeline = result.scalar_one_or_none()

    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline '{pipeline_id}' not found",
        )

    await db.delete(pipeline)
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
    """Run pipeline synchronously.

    Args:
        pipeline_id: Pipeline UUID
        parameters: Pipeline input parameters
        db: Database session

    Returns:
        Pipeline run result

    Raises:
        HTTPException: If pipeline not found
    """
    # Get pipeline
    result = await db.execute(select(Pipeline).where(Pipeline.id == pipeline_id))
    pipeline = result.scalar_one_or_none()

    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline '{pipeline_id}' not found",
        )

    # Create pipeline run
    run_id = str(uuid.uuid4())
    pipeline_run = PipelineRun(
        id=run_id,
        pipeline_id=pipeline_id,
        status=RunStatus.RUNNING,
        parameters=parameters or {},
        started_at=datetime.utcnow(),
    )

    db.add(pipeline_run)
    await db.commit()

    # Execute pipeline
    try:
        # Get final result from async generator
        final_result = None
        async for _, result in execute_pipeline_with_streaming(
            pipeline_id=pipeline_id,
            pipeline_run_id=run_id,
            graph_definition=pipeline.graph_definition,
            pipeline_params=parameters or {},
        ):
            final_result = result

        # Update run status
        if final_result and final_result.success:
            pipeline_run.status = RunStatus.SUCCESS
        else:
            pipeline_run.status = RunStatus.FAILED
            pipeline_run.error_message = (
                final_result.error if final_result else "Unknown error"
            )

    except Exception as e:
        pipeline_run.status = RunStatus.FAILED
        pipeline_run.error_message = str(e)
        await db.commit()
        raise

    pipeline_run.completed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(pipeline_run)

    return pipeline_run


@router.post("/{pipeline_id}/run/stream")
async def run_pipeline_stream(
    pipeline_id: str,
    parameters: dict[str, Any] | None = None,
    db: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Run pipeline with SSE log streaming.

    Args:
        pipeline_id: Pipeline UUID
        parameters: Pipeline input parameters
        db: Database session

    Returns:
        SSE stream of logs and final result
    """
    # Get pipeline
    result = await db.execute(select(Pipeline).where(Pipeline.id == pipeline_id))
    pipeline = result.scalar_one_or_none()

    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline '{pipeline_id}' not found",
        )

    # Create pipeline run
    run_id = str(uuid.uuid4())
    pipeline_run = PipelineRun(
        id=run_id,
        pipeline_id=pipeline_id,
        status=RunStatus.RUNNING,
        parameters=parameters or {},
        started_at=datetime.utcnow(),
    )

    db.add(pipeline_run)
    await db.commit()

    async def generate_sse() -> AsyncGenerator[str, None]:
        """Generate SSE events."""
        try:
            executor = execute_pipeline_with_streaming(
                pipeline_id=pipeline_id,
                pipeline_run_id=run_id,
                graph_definition=pipeline.graph_definition,
                pipeline_params=parameters or {},
            )

            async for logs, result in executor:
                # Stream logs
                for log in logs:
                    event = {
                        "type": "log",
                        "pipeline_run_id": run_id,
                        "node_id": log.node_id,
                        "level": log.level,
                        "message": log.message,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                    yield f"data: {json.dumps(event)}\n\n"

                # Stream final result
                if result is not None:
                    # Update run status
                    if result.success:
                        pipeline_run.status = RunStatus.SUCCESS
                    else:
                        pipeline_run.status = RunStatus.FAILED
                        pipeline_run.error_message = result.error

                    pipeline_run.completed_at = datetime.utcnow()
                    await db.commit()

                    event = {
                        "type": "result",
                        "pipeline_run_id": run_id,
                        "success": result.success,
                        "error": result.error,
                        "node_results": {
                            node_id: {
                                "success": node_result.get("success"),
                                "outputs": node_result.get("outputs"),
                            }
                            for node_id, node_result in result.node_results.items()
                        },
                    }
                    yield f"data: {json.dumps(event)}\n\n"

        except Exception as e:
            pipeline_run.status = RunStatus.FAILED
            pipeline_run.error_message = str(e)
            await db.commit()

            event = {
                "type": "error",
                "pipeline_run_id": run_id,
                "error": str(e),
            }
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


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
