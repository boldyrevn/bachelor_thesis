"""Integration tests for pipeline run API endpoints."""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline import Pipeline
from app.models.pipeline_run import PipelineRun, RunStatus
from app.models.node_run import NodeRun


async def _create_pipeline(db: AsyncSession, name: str = "test_pipeline") -> Pipeline:
    """Helper to create a pipeline in DB."""
    pipeline = Pipeline(
        name=f"{name}_{uuid.uuid4().hex[:8]}",
        description="Test pipeline",
        graph_definition={"nodes": [], "edges": []},
    )
    db.add(pipeline)
    await db.commit()
    await db.refresh(pipeline)
    return pipeline


async def _create_run(db: AsyncSession, pipeline_id: str) -> PipelineRun:
    """Helper to create a pipeline run."""
    run = PipelineRun(
        pipeline_id=pipeline_id,
        status=RunStatus.SUCCESS,
        parameters={"key": "value"},
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def _create_node_run(db: AsyncSession, run_id: str) -> NodeRun:
    """Helper to create a node run."""
    nr = NodeRun(
        pipeline_run_id=run_id,
        node_id="test_node",
        node_type="text_output",
        status=RunStatus.SUCCESS,
        output_values={"text": "hello"},
    )
    db.add(nr)
    await db.commit()
    await db.refresh(nr)
    return nr


@pytest.mark.asyncio
async def test_list_runs_empty(client: AsyncClient, db_session: AsyncSession):
    """Test listing runs for a pipeline with no runs."""
    pipeline = await _create_pipeline(db_session)
    resp = await client.get(f"/api/v1/pipelines/{pipeline.id}/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["runs"] == []


@pytest.mark.asyncio
async def test_list_runs_with_runs(client: AsyncClient, db_session: AsyncSession):
    """Test listing runs returns them."""
    pipeline = await _create_pipeline(db_session)
    run1 = await _create_run(db_session, pipeline.id)
    run2 = await _create_run(db_session, pipeline.id)

    resp = await client.get(f"/api/v1/pipelines/{pipeline.id}/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    # Both runs should be present (order may vary if same timestamp)
    run_ids = {r["id"] for r in data["runs"]}
    assert run1.id in run_ids
    assert run2.id in run_ids


@pytest.mark.asyncio
async def test_list_runs_pipeline_not_found(client: AsyncClient):
    """Test listing runs for non-existent pipeline."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/pipelines/{fake_id}/runs")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_run_detail(client: AsyncClient, db_session: AsyncSession):
    """Test getting a run detail with node runs."""
    pipeline = await _create_pipeline(db_session)
    run = await _create_run(db_session, pipeline.id)
    await _create_node_run(db_session, run.id)

    resp = await client.get(f"/api/v1/pipelines/runs/{run.id}/detail")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run"]["id"] == run.id
    assert data["run"]["status"] == "success"
    assert len(data["node_runs"]) == 1
    assert data["node_runs"][0]["node_id"] == "test_node"
    assert data["node_runs"][0]["status"] == "success"


@pytest.mark.asyncio
async def test_get_run_detail_not_found(client: AsyncClient):
    """Test getting non-existent run."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/pipelines/runs/{fake_id}/detail")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_node_run_logs_not_found(client: AsyncClient):
    """Test getting logs for non-existent node run."""
    fake_run = str(uuid.uuid4())
    fake_node = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/pipelines/runs/{fake_run}/nodes/{fake_node}/logs")
    assert resp.status_code == 404
