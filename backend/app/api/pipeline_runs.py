"""Pipeline run API endpoints for listing and viewing runs."""

import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.core.config import settings
from app.models.node_run import NodeRun
from app.models.pipeline_run import PipelineRun, RunStatus
from app.models.pipeline_version import PipelineVersion

router = APIRouter(prefix="/api/v1/pipelines", tags=["pipeline-runs"])

# Separate router for global runs endpoint (must be registered before parameterized routes)
global_runs_router = APIRouter(prefix="/api/v1", tags=["pipeline-runs"])


@global_runs_router.get("/pipelines/runs")
async def list_all_runs(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """List all pipeline runs across all pipelines.

    Args:
        limit: Max number of runs to return
        offset: Offset for pagination
        db: Database session

    Returns:
        List of pipeline runs with count
    """
    result = await db.execute(
        select(PipelineRun)
        .order_by(PipelineRun.started_at.desc())
        .offset(offset)
        .limit(limit)
    )
    runs = result.scalars().all()

    # Efficient count using COUNT(*)
    count_result = await db.execute(select(func.count(PipelineRun.id)))
    total = count_result.scalar() or 0

    # Collect version_ids to look up pipeline_ids
    version_ids = list({r.version_id for r in runs})
    if version_ids:
        versions_result = await db.execute(
            select(PipelineVersion.id, PipelineVersion.pipeline_id).where(
                PipelineVersion.id.in_(version_ids)
            )
        )
        version_to_pipeline = {row[0]: row[1] for row in versions_result}
    else:
        version_to_pipeline = {}

    return {
        "runs": [
            _run_to_dict(run, version_to_pipeline.get(run.version_id)) for run in runs
        ],
        "total": total,
    }


@router.get("/{pipeline_id}/runs")
async def list_pipeline_runs(
    pipeline_id: str,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """List all runs for a pipeline (across all versions).

    Args:
        pipeline_id: Logical pipeline UUID
        limit: Max number of runs to return
        offset: Offset for pagination
        db: Database session

    Returns:
        List of pipeline runs with count
    """
    # Get all version IDs for this pipeline
    versions_result = await db.execute(
        select(PipelineVersion.id).where(PipelineVersion.pipeline_id == pipeline_id)
    )
    version_ids = [row[0] for row in versions_result.all()]

    if not version_ids:
        return {"runs": [], "total": 0}

    # Get runs for all versions of this pipeline
    result = await db.execute(
        select(PipelineRun)
        .where(PipelineRun.version_id.in_(version_ids))
        .order_by(PipelineRun.started_at.desc())
        .offset(offset)
        .limit(limit)
    )
    runs = result.scalars().all()

    # Efficient count using COUNT(*)
    count_result = await db.execute(
        select(func.count(PipelineRun.id)).where(PipelineRun.version_id.in_(version_ids))
    )
    total = count_result.scalar() or 0

    return {
        "runs": [_run_to_dict(run, pipeline_id=pipeline_id) for run in runs],
        "total": total,
    }


@router.get("/runs/{run_id}/detail")
async def get_pipeline_run_detail(
    run_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Get a pipeline run with its node runs.

    Args:
        run_id: Pipeline run UUID
        db: Database session

    Returns:
        Pipeline run with node_runs included
    """
    # Get pipeline run
    result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline run '{run_id}' not found",
        )

    # Get node runs
    result = await db.execute(select(NodeRun).where(NodeRun.pipeline_run_id == run_id))
    node_runs = result.scalars().all()

    # Look up pipeline_id from version for log path resolution
    pv_result = await db.execute(
        select(PipelineVersion.pipeline_id).where(PipelineVersion.id == run.version_id)
    )
    pipeline_id = pv_result.scalar_one_or_none()

    return {
        "run": _run_to_dict(run, pipeline_id),
        "node_runs": [_node_run_to_dict(nr, pipeline_id) for nr in node_runs],
    }


@router.get("/runs/{run_id}/nodes/{node_id}/logs")
async def get_node_run_logs(
    run_id: str,
    node_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Get log contents for a specific node run.

    Reads from log file on disk.
    Log path: LOG_DIR/run_logs/<version_id>/<node_id>/<run_id>.log

    Args:
        run_id: Pipeline run UUID
        node_id: Node ID within the run
        db: Database session

    Returns:
        Log file contents
    """
    # Get version_id directly from the run record
    run_result = await db.execute(
        select(PipelineRun.version_id).where(PipelineRun.id == run_id)
    )
    version_id = run_result.scalar_one_or_none()
    if not version_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline run '{run_id}' not found",
        )

    log_file = os.path.join(
        settings.LOG_DIR, "run_logs", version_id, node_id, f"{run_id}.log"
    )

    if not os.path.exists(log_file):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Log file for node '{node_id}' not found",
        )

    with open(log_file, "r") as f:
        content = f.read()

    return {"logs": content}


def _run_to_dict(run: PipelineRun, pipeline_id: str | None = None) -> dict:
    """Convert PipelineRun to dict."""
    duration = None
    if run.started_at and run.completed_at:
        delta = run.completed_at - run.started_at
        duration = delta.total_seconds()

    result = {
        "id": run.id,
        "version_id": run.version_id,
        "status": run.status.value if isinstance(run.status, RunStatus) else run.status,
        "parameters": run.parameters,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "error_message": run.error_message,
        "duration_seconds": duration,
    }
    if pipeline_id:
        result["pipeline_id"] = pipeline_id
    return result


def _node_run_to_dict(nr: NodeRun, pipeline_id: str | None = None) -> dict:
    """Convert NodeRun to dict."""
    result = {
        "id": nr.id,
        "pipeline_run_id": nr.pipeline_run_id,
        "node_id": nr.node_id,
        "node_type": nr.node_type,
        "status": nr.status.value if isinstance(nr.status, RunStatus) else nr.status,
        "output_values": nr.output_values,
        "started_at": nr.started_at.isoformat() if nr.started_at else None,
        "completed_at": nr.completed_at.isoformat() if nr.completed_at else None,
    }
    if pipeline_id:
        result["pipeline_id"] = pipeline_id
    return result


__all__ = ["pipeline_runs_router", "global_runs_router"]

pipeline_runs_router = router
