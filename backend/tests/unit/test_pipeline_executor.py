"""Unit tests for pipeline executor."""

import pytest

from app.orchestration.pipeline_executor import (
    PipelineExecutionContext,
    PipelineExecutor,
    PipelineExecutionResult,
    execute_pipeline,
)


class TestPipelineExecutionContext:
    """Tests for PipelineExecutionContext."""

    def test_context_creation(self):
        """Test basic context creation."""
        context = PipelineExecutionContext(
            pipeline_id="pipeline-123",
            pipeline_run_id="run-456",
        )

        assert context.pipeline_id == "pipeline-123"
        assert context.pipeline_run_id == "run-456"
        assert context.pipeline_params == {}
        assert context.node_outputs == {}
        assert context.node_logs == {}

    def test_context_with_params(self):
        """Test context with pipeline parameters."""
        context = PipelineExecutionContext(
            pipeline_id="pipeline-123",
            pipeline_run_id="run-456",
            pipeline_params={"date": "2024-01-01", "env": "prod"},
        )

        assert context.pipeline_params["date"] == "2024-01-01"
        assert context.pipeline_params["env"] == "prod"


class TestPipelineExecutionResult:
    """Tests for PipelineExecutionResult."""

    def test_success_result(self):
        """Test successful result."""
        result = PipelineExecutionResult(
            success=True,
            pipeline_id="pipeline-123",
            pipeline_run_id="run-456",
            node_results={"node-1": {"outputs": {"text": "Hello"}}},
        )

        assert result.success is True
        assert result.pipeline_id == "pipeline-123"
        assert result.error is None

    def test_error_result(self):
        """Test error result."""
        result = PipelineExecutionResult(
            success=False,
            pipeline_id="pipeline-123",
            pipeline_run_id="run-456",
            error="Something went wrong",
        )

        assert result.success is False
        assert result.error == "Something went wrong"


class TestPipelineExecutorTemplateResolution:
    """Tests for template resolution in PipelineExecutor."""

    def test_resolve_node_output_template(self):
        """Test resolving {{ node_id.output_name }} template."""
        executor = PipelineExecutor({"nodes": [], "edges": []})
        context = PipelineExecutionContext(
            pipeline_id="p1",
            pipeline_run_id="r1",
            node_outputs={"node-a": {"text": "Hello from A"}},
        )

        result = executor._resolve_string_templates(
            "Message: {{ node-a.text }}", context
        )

        assert result == "Message: Hello from A"

    def test_resolve_params_template(self):
        """Test resolving {{ params.param_name }} template."""
        executor = PipelineExecutor({"nodes": [], "edges": []})
        context = PipelineExecutionContext(
            pipeline_id="p1",
            pipeline_run_id="r1",
            pipeline_params={"date": "2024-01-15", "env": "prod"},
        )

        result = executor._resolve_string_templates(
            "Date: {{ params.date }}, Env: {{ params.env }}", context
        )

        assert result == "Date: 2024-01-15, Env: prod"

    def test_resolve_mixed_templates(self):
        """Test resolving mixed node and params templates."""
        executor = PipelineExecutor({"nodes": [], "edges": []})
        context = PipelineExecutionContext(
            pipeline_id="p1",
            pipeline_run_id="r1",
            pipeline_params={"suffix": "World"},
            node_outputs={"greeting": {"text": "Hello"}},
        )

        result = executor._resolve_string_templates(
            "{{ greeting.text }}, {{ params.suffix }}!", context
        )

        assert result == "Hello, World!"

    def test_resolve_unresolved_template_kept(self):
        """Test that unresolved templates are kept as-is."""
        executor = PipelineExecutor({"nodes": [], "edges": []})
        context = PipelineExecutionContext(
            pipeline_id="p1",
            pipeline_run_id="r1",
        )

        result = executor._resolve_string_templates(
            "Value: {{ nonexistent.output }}", context
        )

        assert result == "Value: {{ nonexistent.output }}"

    def test_resolve_nested_dict(self):
        """Test resolving templates in nested dictionary."""
        executor = PipelineExecutor({"nodes": [], "edges": []})
        context = PipelineExecutionContext(
            pipeline_id="p1",
            pipeline_run_id="r1",
            node_outputs={"node-a": {"path": "s3://bucket/file"}},
        )

        node_data = {
            "config": {
                "input_path": "{{ node-a.path }}",
                "nested": {"output": "{{ node-a.path }}/output"},
            }
        }

        result = executor._resolve_templates(node_data, context)

        assert result["config"]["input_path"] == "s3://bucket/file"
        assert result["config"]["nested"]["output"] == "s3://bucket/file/output"

    def test_resolve_list_with_templates(self):
        """Test resolving templates in list."""
        executor = PipelineExecutor({"nodes": [], "edges": []})
        context = PipelineExecutionContext(
            pipeline_id="p1",
            pipeline_run_id="r1",
            node_outputs={"node-a": {"value": "A"}, "node-b": {"value": "B"}},
        )

        node_data = {"items": ["{{ node-a.value }}", "{{ node-b.value }}"]}

        result = executor._resolve_templates(node_data, context)

        assert result["items"] == ["A", "B"]


class TestPipelineExecutorParamsExtraction:
    """Tests for pipeline parameter extraction."""

    def test_extract_params_from_pipeline_params_node(self):
        """Test extracting params from PipelineParams node."""
        graph = {
            "nodes": [
                {
                    "id": "params-1",
                    "type": "PipelineParams",
                    "data": {
                        "parameters": [
                            {"name": "date", "type": "string", "default": "2024-01-01"},
                            {"name": "env", "type": "string", "default": "dev"},
                        ]
                    },
                }
            ],
            "edges": [],
        }

        executor = PipelineExecutor(graph)
        # Mock resolved graph for testing
        from app.orchestration.graph_resolver import ResolvedGraph

        resolved = ResolvedGraph(nodes={}, execution_order=[])
        params = executor._extract_pipeline_params(resolved)

        assert params["date"] == "2024-01-01"
        assert params["env"] == "dev"

    def test_extract_params_override_with_provided(self):
        """Test that provided params override defaults."""
        graph = {
            "nodes": [
                {
                    "id": "params-1",
                    "type": "PipelineParams",
                    "data": {
                        "parameters": [
                            {"name": "date", "type": "string", "default": "2024-01-01"}
                        ]
                    },
                }
            ],
            "edges": [],
        }

        executor = PipelineExecutor(graph, pipeline_params={"date": "2024-06-15"})
        from app.orchestration.graph_resolver import ResolvedGraph

        resolved = ResolvedGraph(nodes={}, execution_order=[])
        params = executor._extract_pipeline_params(resolved)

        assert params["date"] == "2024-06-15"


class TestPipelineExecutorExecution:
    """Tests for pipeline execution."""

    @pytest.mark.asyncio
    async def test_execute_single_node_pipeline(self):
        """Test executing pipeline with single node."""
        graph = {
            "nodes": [
                {
                    "id": "node-1",
                    "type": "text_output",
                    "data": {"message": "Hello from pipeline!"},
                }
            ],
            "edges": [],
        }

        executor = PipelineExecutor(graph)
        result = await executor.execute(
            pipeline_id="pipeline-test-1",
            pipeline_run_id="run-test-1",
        )

        assert result.success is True
        assert "node-1" in result.node_results
        assert (
            result.node_results["node-1"]["outputs"]["text"] == "Hello from pipeline!"
        )

        await executor.close()

    @pytest.mark.asyncio
    async def test_execute_two_node_pipeline(self):
        """Test executing pipeline with two nodes."""
        graph = {
            "nodes": [
                {
                    "id": "node-1",
                    "type": "text_output",
                    "data": {"message": "First node"},
                },
                {
                    "id": "node-2",
                    "type": "text_output",
                    "data": {"message": "Second node"},
                },
            ],
            "edges": [
                {"id": "e1", "source": "node-1", "target": "node-2"},
            ],
        }

        executor = PipelineExecutor(graph)
        result = await executor.execute(
            pipeline_id="pipeline-test-2",
            pipeline_run_id="run-test-2",
        )

        assert result.success is True
        assert "node-1" in result.node_results
        assert "node-2" in result.node_results

        await executor.close()

    @pytest.mark.asyncio
    async def test_execute_pipeline_with_template_resolution(self):
        """Test executing pipeline with template resolution between nodes."""
        graph = {
            "nodes": [
                {
                    "id": "node-1",
                    "type": "text_output",
                    "data": {"message": "Hello from upstream!"},
                },
                {
                    "id": "node-2",
                    "type": "text_output",
                    "data": {"message": "Received: {{ node-1.text }}"},
                },
            ],
            "edges": [
                {"id": "e1", "source": "node-1", "target": "node-2"},
            ],
        }

        executor = PipelineExecutor(graph)
        result = await executor.execute(
            pipeline_id="pipeline-test-3",
            pipeline_run_id="run-test-3",
        )

        assert result.success is True
        assert (
            result.node_results["node-1"]["outputs"]["text"] == "Hello from upstream!"
        )
        assert (
            result.node_results["node-2"]["outputs"]["text"]
            == "Received: Hello from upstream!"
        )

        await executor.close()

    @pytest.mark.asyncio
    async def test_execute_pipeline_with_cycle_fails(self):
        """Test that pipeline with cycle fails gracefully."""
        graph = {
            "nodes": [
                {"id": "node-1", "type": "text_output", "data": {}},
                {"id": "node-2", "type": "text_output", "data": {}},
            ],
            "edges": [
                {"id": "e1", "source": "node-1", "target": "node-2"},
                {"id": "e2", "source": "node-2", "target": "node-1"},
            ],
        }

        executor = PipelineExecutor(graph)
        result = await executor.execute(
            pipeline_id="pipeline-test-4",
            pipeline_run_id="run-test-4",
        )

        assert result.success is False
        assert result.error is not None
        assert "Cycle detected" in result.error

        await executor.close()

    @pytest.mark.asyncio
    async def test_execute_with_streaming(self):
        """Test pipeline execution with log streaming."""
        graph = {
            "nodes": [
                {
                    "id": "node-1",
                    "type": "text_output",
                    "data": {"message": "Streaming test"},
                }
            ],
            "edges": [],
        }

        executor = PipelineExecutor(graph)
        logs_received = []
        final_result = None

        async for logs, result in executor.execute_with_streaming(
            pipeline_id="pipeline-stream-1",
            pipeline_run_id="run-stream-1",
        ):
            if logs:
                logs_received.extend(logs)
            else:
                final_result = result

        assert len(logs_received) > 0
        assert final_result is not None
        assert final_result.success is True

        await executor.close()


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @pytest.mark.asyncio
    async def test_execute_pipeline_function(self):
        """Test execute_pipeline convenience function."""
        graph = {
            "nodes": [
                {
                    "id": "node-1",
                    "type": "text_output",
                    "data": {"message": "Convenience test"},
                }
            ],
            "edges": [],
        }

        result = await execute_pipeline(
            pipeline_id="pipeline-conv-1",
            pipeline_run_id="run-conv-1",
            graph_definition=graph,
        )

        assert result.success is True
        assert result.node_results["node-1"]["outputs"]["text"] == "Convenience test"
