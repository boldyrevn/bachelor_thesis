"""Integration tests for Pipeline CRUD API."""

import json

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline import Pipeline
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
        assert "graph_definition" in data

        # Verify in database
        result = await db_session.execute(
            select(Pipeline).where(Pipeline.id == data["id"])
        )
        pipeline = result.scalar_one_or_none()
        assert pipeline is not None
        assert pipeline.name == "Test Pipeline"

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
        from sqlalchemy import text

        await db_session.execute(text("DELETE FROM pipelines"))
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
        pipeline_id = create_response.json()["id"]

        # Get pipeline
        response = await client.get(f"/api/v1/pipelines/{pipeline_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == pipeline_id
        assert data["name"] == "Get Test Pipeline"

    @pytest.mark.asyncio
    async def test_get_pipeline_not_found(self, client: AsyncClient):
        """Test getting non-existent pipeline."""
        response = await client.get(
            "/api/v1/pipelines/00000000-0000-0000-0000-000000000000"
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_pipeline(self, client: AsyncClient, db_session: AsyncSession):
        """Test updating pipeline."""
        # Create pipeline
        payload = {"name": "Update Test", "description": "Original"}
        create_response = await client.post("/api/v1/pipelines", json=payload)
        pipeline_id = create_response.json()["id"]

        # Update pipeline
        update_payload = {"name": "Updated Name", "description": "Updated description"}
        response = await client.put(
            f"/api/v1/pipelines/{pipeline_id}", json=update_payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_delete_pipeline(self, client: AsyncClient, db_session: AsyncSession):
        """Test deleting pipeline."""
        # Create pipeline
        payload = {"name": "Delete Test", "description": "To delete"}
        create_response = await client.post("/api/v1/pipelines", json=payload)
        pipeline_id = create_response.json()["id"]

        # Delete pipeline
        response = await client.delete(f"/api/v1/pipelines/{pipeline_id}")

        assert response.status_code == 204

        # Verify deleted
        result = await db_session.execute(
            select(Pipeline).where(Pipeline.id == pipeline_id)
        )
        pipeline = result.scalar_one_or_none()
        assert pipeline is None

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
        pipeline_id = create_response.json()["id"]

        # Run pipeline
        run_response = await client.post(
            f"/api/v1/pipelines/{pipeline_id}/run", json={"test_param": "value"}
        )

        assert run_response.status_code == 201
        data = run_response.json()
        assert data["pipeline_id"] == pipeline_id
        assert data["status"] == "success"
        assert data["parameters"] == {"test_param": "value"}

        # Verify run in database
        result = await db_session.execute(
            select(PipelineRun).where(PipelineRun.pipeline_id == pipeline_id)
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
        from sqlalchemy import update

        # Create pipeline without graph validation
        payload = {"name": "Cycle Run Pipeline"}
        create_response = await client.post("/api/v1/pipelines", json=payload)
        pipeline_id = create_response.json()["id"]

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
            update(Pipeline)
            .where(Pipeline.id == pipeline_id)
            .values(graph_definition=cycle_graph)
        )
        await db_session.commit()

        # Run pipeline - should fail with cycle error
        run_response = await client.post(f"/api/v1/pipelines/{pipeline_id}/run")

        assert run_response.status_code == 201
        data = run_response.json()
        assert data["status"] == "failed"
        assert "Cycle detected" in data["error_message"]

    @pytest.mark.asyncio
    async def test_run_pipeline_stream(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test running pipeline with SSE streaming."""
        # Create pipeline with two nodes
        payload = {
            "name": "Stream Test Pipeline",
            "graph_definition": {
                "nodes": [
                    {
                        "id": "node-1",
                        "type": "text_output",
                        "data": {"message": "First"},
                    },
                    {
                        "id": "node-2",
                        "type": "text_output",
                        "data": {"message": "{{ node-1.text }} + Second"},
                    },
                ],
                "edges": [{"id": "e1", "source": "node-1", "target": "node-2"}],
            },
        }
        create_response = await client.post("/api/v1/pipelines", json=payload)
        pipeline_id = create_response.json()["id"]

        # Run pipeline with streaming
        events = []
        async with client.stream(
            "POST", f"/api/v1/pipelines/{pipeline_id}/run/stream"
        ) as response:
            assert response.status_code == 200
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    event_data = json.loads(line[6:])  # Remove "data: " prefix
                    events.append(event_data)

        # Verify events
        log_events = [e for e in events if e.get("type") == "log"]
        result_events = [e for e in events if e.get("type") == "result"]

        assert len(log_events) > 0, "Expected log events"
        assert len(result_events) == 1, "Expected one result event"

        # Verify result
        result = result_events[0]
        assert result["success"] is True
        assert "node-1" in result["node_results"]
        assert "node-2" in result["node_results"]

        # Verify template resolution worked
        assert result["node_results"]["node-2"]["outputs"]["text"] == "First + Second"

    @pytest.mark.asyncio
    async def test_run_pipeline_stream_log_details(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that SSE stream contains detailed log information."""
        # Create pipeline with known node configuration
        payload = {
            "name": "Log Details Pipeline",
            "graph_definition": {
                "nodes": [
                    {
                        "id": "test-node",
                        "type": "text_output",
                        "data": {"message": "Test message"},
                    }
                ],
                "edges": [],
            },
        }
        create_response = await client.post("/api/v1/pipelines", json=payload)
        pipeline_id = create_response.json()["id"]

        # Run pipeline with streaming
        log_events = []
        async with client.stream(
            "POST", f"/api/v1/pipelines/{pipeline_id}/run/stream"
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    event_data = json.loads(line[6:])
                    if event_data.get("type") == "log":
                        log_events.append(event_data)

        # Verify log event structure
        assert len(log_events) > 0, "Expected log events"

        for log in log_events:
            # Verify required fields
            assert "pipeline_run_id" in log
            assert "node_id" in log
            assert "level" in log
            assert "message" in log
            assert "timestamp" in log

            # Verify field values
            assert log["node_id"] == "test-node"
            assert log["level"] in ["INFO", "ERROR", "DEBUG", "WARNING"]
            assert isinstance(log["message"], str)
            assert len(log["message"]) > 0

        # Verify expected log messages from TextOutputNode
        all_messages = [log["message"] for log in log_events]
        assert any("Starting text output node" in msg for msg in all_messages)
        assert any("completed successfully" in msg for msg in all_messages)

    @pytest.mark.asyncio
    async def test_run_pipeline_stream_log_sequence(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that logs arrive in correct sequence."""
        # Create pipeline
        payload = {
            "name": "Log Sequence Pipeline",
            "graph_definition": {
                "nodes": [
                    {
                        "id": "node-a",
                        "type": "text_output",
                        "data": {"message": "A"},
                    },
                    {
                        "id": "node-b",
                        "type": "text_output",
                        "data": {"message": "{{ node-a.text }}-B"},
                    },
                ],
                "edges": [{"id": "e1", "source": "node-a", "target": "node-b"}],
            },
        }
        create_response = await client.post("/api/v1/pipelines", json=payload)
        pipeline_id = create_response.json()["id"]

        # Run pipeline with streaming
        log_sequence = []
        async with client.stream(
            "POST", f"/api/v1/pipelines/{pipeline_id}/run/stream"
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    event_data = json.loads(line[6:])
                    if event_data.get("type") == "log":
                        log_sequence.append(
                            {
                                "node_id": event_data["node_id"],
                                "message": event_data["message"],
                            }
                        )

        # Verify node-a logs come before node-b logs
        node_a_indices = [
            i for i, log in enumerate(log_sequence) if log["node_id"] == "node-a"
        ]
        node_b_indices = [
            i for i, log in enumerate(log_sequence) if log["node_id"] == "node-b"
        ]

        assert len(node_a_indices) > 0
        assert len(node_b_indices) > 0

        # All node-a logs should come before all node-b logs
        assert max(node_a_indices) < min(node_b_indices)

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
        pipeline_id = create_response.json()["id"]

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
        pipeline_id = create_response.json()["id"]

        run_response = await client.post(f"/api/v1/pipelines/{pipeline_id}/run")
        run_id = run_response.json()["id"]

        # Get run
        get_response = await client.get(f"/api/v1/pipelines/runs/{run_id}")

        assert get_response.status_code == 200
        data = get_response.json()
        assert data["id"] == run_id
        assert data["pipeline_id"] == pipeline_id
        assert data["status"] == "success"

    @pytest.mark.asyncio
    async def test_get_pipeline_run_not_found(self, client: AsyncClient):
        """Test getting non-existent pipeline run."""
        response = await client.get(
            "/api/v1/pipelines/runs/00000000-0000-0000-0000-000000000000"
        )

        assert response.status_code == 404
