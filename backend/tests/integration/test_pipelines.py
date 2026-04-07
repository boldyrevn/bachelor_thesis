"""Integration tests for Pipeline CRUD API."""

import json

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline_version import PipelineVersion
from app.models.pipeline_run import PipelineRun, RunStatus


class TestPipelineCRUD:
    """Integration tests for Pipeline CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_create_pipeline(self, client: AsyncClient, db_session: AsyncSession):
        """Test creating a new pipeline."""
        payload = {
            "name": "Test Pipeline",
            "description": "A test pipeline",
            "graph_definition": {
                "nodes": [
                    {
                        "id": "node-1",
                        "type": "text_output",
                        "data": {"message": "Hello"},
                    }
                ],
                "edges": [],
            },
        }

        response = await client.post("/api/v1/pipelines", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Pipeline"
        assert data["description"] == "A test pipeline"
        assert "id" in data
        assert "pipeline_id" in data
        assert "graph_definition" in data
        assert data["version"] == 1
        assert data["is_current"] is True

        # Verify in database
        result = await db_session.execute(
            select(PipelineVersion).where(PipelineVersion.id == data["id"])
        )
        version = result.scalar_one_or_none()
        assert version is not None
        assert version.name == "Test Pipeline"
        assert version.pipeline_id == data["pipeline_id"]

    @pytest.mark.asyncio
    async def test_create_pipeline_duplicate_name_fails(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that creating pipeline with duplicate name fails."""
        # Create first pipeline
        payload1 = {"name": "Duplicate Test", "description": "First"}
        await client.post("/api/v1/pipelines", json=payload1)

        # Try to create second with same name
        payload2 = {"name": "Duplicate Test", "description": "Second"}
        response = await client.post("/api/v1/pipelines", json=payload2)

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_pipeline_invalid_graph(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that creating pipeline with invalid graph (cycle) fails."""
        payload = {
            "name": "Invalid Graph Pipeline",
            "graph_definition": {
                "nodes": [
                    {"id": "A", "type": "text_output", "data": {}},
                    {"id": "B", "type": "text_output", "data": {}},
                ],
                "edges": [
                    {"id": "e1", "source": "A", "target": "B"},
                    {"id": "e2", "source": "B", "target": "A"},
                ],
            },
        }

        response = await client.post("/api/v1/pipelines", json=payload)

        assert response.status_code == 400
        assert "Cycle detected" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_pipelines(self, client: AsyncClient, db_session: AsyncSession):
        """Test listing all pipelines."""
        # Clean up existing pipelines to avoid test interference
        await db_session.execute(text("DELETE FROM pipeline_runs"))
        await db_session.execute(text("DELETE FROM pipeline_versions"))
        await db_session.commit()

        # Create test pipelines
        for i in range(3):
            payload = {"name": f"Pipeline {i}", "description": f"Test {i}"}
            await client.post("/api/v1/pipelines", json=payload)

        response = await client.get("/api/v1/pipelines")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        names = [p["name"] for p in data]
        assert "Pipeline 0" in names
        assert "Pipeline 1" in names
        assert "Pipeline 2" in names

    @pytest.mark.asyncio
    async def test_get_pipeline(self, client: AsyncClient, db_session: AsyncSession):
        """Test getting pipeline by ID."""
        # Create pipeline
        payload = {"name": "Get Test Pipeline", "description": "Test"}
        create_response = await client.post("/api/v1/pipelines", json=payload)
        pipeline_id = create_response.json()["pipeline_id"]

        # Get pipeline
        response = await client.get(f"/api/v1/pipelines/{pipeline_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == create_response.json()["id"]
        assert data["name"] == "Get Test Pipeline"

    @pytest.mark.asyncio
    async def test_get_pipeline_not_found(self, client: AsyncClient):
        """Test getting non-existent pipeline."""
        response = await client.get(
            "/api/v1/pipelines/00000000-0000-0000-0000-000000000000"
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_pipeline_creates_new_version(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that updating pipeline creates a new version."""
        # Create pipeline
        payload = {"name": "Update Test", "description": "Original"}
        create_response = await client.post("/api/v1/pipelines", json=payload)
        pipeline_id = create_response.json()["pipeline_id"]
        v1_id = create_response.json()["id"]

        # Update pipeline
        update_payload = {"name": "Updated Name", "description": "Updated description"}
        response = await client.put(
            f"/api/v1/pipelines/{pipeline_id}", json=update_payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "Updated description"
        assert data["version"] == 2
        assert data["id"] != v1_id  # New version has different ID
        assert data["is_current"] is True

        # Verify old version is no longer current
        result = await db_session.execute(
            select(PipelineVersion).where(PipelineVersion.id == v1_id)
        )
        old_version = result.scalar_one_or_none()
        assert old_version is not None
        assert old_version.is_current is False

    @pytest.mark.asyncio
    async def test_list_pipeline_versions(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test listing all versions of a pipeline."""
        # Create pipeline
        payload = {"name": "Versions Test", "description": "Original"}
        create_response = await client.post("/api/v1/pipelines", json=payload)
        pipeline_id = create_response.json()["pipeline_id"]

        # Update pipeline twice
        await client.put(
            f"/api/v1/pipelines/{pipeline_id}",
            json={"description": "Updated 1"},
        )
        await client.put(
            f"/api/v1/pipelines/{pipeline_id}",
            json={"description": "Updated 2"},
        )

        # List versions
        response = await client.get(f"/api/v1/pipelines/{pipeline_id}/versions")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        # Sorted by created_at desc (newest first)
        assert data[0]["version"] == 3
        assert data[1]["version"] == 2
        assert data[2]["version"] == 1
        assert data[0]["is_current"] is True
        assert data[1]["is_current"] is False
        assert data[2]["is_current"] is False

    @pytest.mark.asyncio
    async def test_get_pipeline_version(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test getting a specific version of a pipeline."""
        # Create pipeline
        payload = {"name": "Get Version Test"}
        create_response = await client.post("/api/v1/pipelines", json=payload)
        pipeline_id = create_response.json()["pipeline_id"]
        v1_id = create_response.json()["id"]

        # Update pipeline
        update_response = await client.put(
            f"/api/v1/pipelines/{pipeline_id}",
            json={"description": "Updated"},
        )
        v2_id = update_response.json()["id"]

        # Get v1
        response = await client.get(f"/api/v1/pipelines/{pipeline_id}/versions/{v1_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == v1_id
        assert data["version"] == 1
        assert data["is_current"] is False

        # Get v2
        response = await client.get(f"/api/v1/pipelines/{pipeline_id}/versions/{v2_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == v2_id
        assert data["version"] == 2
        assert data["is_current"] is True

    @pytest.mark.asyncio
    async def test_delete_pipeline(self, client: AsyncClient, db_session: AsyncSession):
        """Test deleting pipeline and all its versions."""
        # Create pipeline
        payload = {"name": "Delete Test", "description": "To delete"}
        create_response = await client.post("/api/v1/pipelines", json=payload)
        pipeline_id = create_response.json()["pipeline_id"]

        # Update to create another version
        await client.put(
            f"/api/v1/pipelines/{pipeline_id}",
            json={"description": "Updated"},
        )

        # Delete pipeline
        response = await client.delete(f"/api/v1/pipelines/{pipeline_id}")

        assert response.status_code == 204

        # Verify all versions deleted
        result = await db_session.execute(
            select(PipelineVersion).where(PipelineVersion.pipeline_id == pipeline_id)
        )
        versions = result.scalars().all()
        assert len(versions) == 0

    @pytest.mark.asyncio
    async def test_delete_pipeline_not_found(self, client: AsyncClient):
        """Test deleting non-existent pipeline."""
        response = await client.delete(
            "/api/v1/pipelines/00000000-0000-0000-0000-000000000000"
        )

        assert response.status_code == 404


class TestPipelineRun:
    """Integration tests for Pipeline execution endpoints."""

    @pytest.mark.asyncio
    async def test_run_pipeline_sync(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test running pipeline synchronously."""
        # Create pipeline with single node
        payload = {
            "name": "Run Test Pipeline",
            "graph_definition": {
                "nodes": [
                    {
                        "id": "node-1",
                        "type": "text_output",
                        "data": {"message": "Hello from run!"},
                    }
                ],
                "edges": [],
            },
        }
        create_response = await client.post("/api/v1/pipelines", json=payload)
        pipeline_id = create_response.json()["pipeline_id"]
        version_id = create_response.json()["id"]

        # Run pipeline
        run_response = await client.post(
            f"/api/v1/pipelines/{pipeline_id}/run", json={"test_param": "value"}
        )

        assert run_response.status_code == 201
        data = run_response.json()
        assert data["version_id"] == version_id
        assert data["status"] == "success"
        assert data["parameters"] == {"test_param": "value"}

        # Verify run in database
        result = await db_session.execute(
            select(PipelineRun).where(PipelineRun.version_id == version_id)
        )
        runs = result.scalars().all()
        assert len(runs) == 1
        assert runs[0].status == RunStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_run_pipeline_not_found(self, client: AsyncClient):
        """Test running non-existent pipeline."""
        response = await client.post(
            "/api/v1/pipelines/00000000-0000-0000-0000-000000000000/run"
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_run_pipeline_with_cycle_fails(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that running pipeline with cycle fails gracefully.

        Note: We bypass graph validation at creation time by not providing
        graph_definition, then manually update it to test runtime cycle detection.
        """
        # Create pipeline without graph validation
        payload = {"name": "Cycle Run Pipeline"}
        create_response = await client.post("/api/v1/pipelines", json=payload)
        pipeline_id = create_response.json()["pipeline_id"]
        version_id = create_response.json()["id"]

        # Manually update graph_definition with cycle in database
        cycle_graph = {
            "nodes": [
                {"id": "A", "type": "text_output", "data": {}},
                {"id": "B", "type": "text_output", "data": {}},
            ],
            "edges": [
                {"id": "e1", "source": "A", "target": "B"},
                {"id": "e2", "source": "B", "target": "A"},
            ],
        }
        await db_session.execute(
            text(
                "UPDATE pipeline_versions SET graph_definition = :graph WHERE id = :id"
            ),
            {"graph": json.dumps(cycle_graph), "id": version_id},
        )
        await db_session.commit()

        # Run pipeline - should fail with cycle error
        run_response = await client.post(f"/api/v1/pipelines/{pipeline_id}/run")

        assert run_response.status_code == 201
        data = run_response.json()
        assert data["status"] == "failed"
        assert "Cycle detected" in data["error_message"]

    @pytest.mark.asyncio
    async def test_run_pipeline_stream_with_params(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that pipeline parameters are passed correctly."""
        # Create pipeline with params node
        payload = {
            "name": "Params Pipeline",
            "graph_definition": {
                "nodes": [
                    {
                        "id": "params-1",
                        "type": "PipelineParams",
                        "data": {
                            "parameters": [
                                {
                                    "name": "greeting",
                                    "type": "string",
                                    "default": "Hello",
                                }
                            ]
                        },
                    },
                    {
                        "id": "node-1",
                        "type": "text_output",
                        "data": {"message": "{{ params.greeting }} from params!"},
                    },
                ],
                "edges": [{"id": "e1", "source": "params-1", "target": "node-1"}],
            },
        }
        create_response = await client.post("/api/v1/pipelines", json=payload)
        pipeline_id = create_response.json()["pipeline_id"]

        # Run pipeline with custom parameter
        run_response = await client.post(
            f"/api/v1/pipelines/{pipeline_id}/run",
            json={"greeting": "Custom greeting"},
        )

        assert run_response.status_code == 201
        data = run_response.json()
        assert data["status"] == "success"
        assert data["parameters"] == {"greeting": "Custom greeting"}

    @pytest.mark.asyncio
    async def test_get_pipeline_run(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test getting pipeline run by ID."""
        # Create and run pipeline
        payload = {
            "name": "Get Run Test Pipeline",
            "graph_definition": {
                "nodes": [
                    {"id": "node-1", "type": "text_output", "data": {"message": "Test"}}
                ],
                "edges": [],
            },
        }
        create_response = await client.post("/api/v1/pipelines", json=payload)
        pipeline_id = create_response.json()["pipeline_id"]
        version_id = create_response.json()["id"]

        run_response = await client.post(f"/api/v1/pipelines/{pipeline_id}/run")
        run_id = run_response.json()["id"]

        # Get run
        get_response = await client.get(f"/api/v1/pipelines/runs/{run_id}")

        assert get_response.status_code == 200
        data = get_response.json()
        assert data["id"] == run_id
        assert data["version_id"] == version_id
        assert data["status"] == "success"

    @pytest.mark.asyncio
    async def test_get_pipeline_run_not_found(self, client: AsyncClient):
        """Test getting non-existent pipeline run."""
        response = await client.get(
            "/api/v1/pipelines/runs/00000000-0000-0000-0000-000000000000"
        )

        assert response.status_code == 404
