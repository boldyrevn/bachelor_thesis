"""Pipeline executor for orchestrating node execution.

Executes nodes in topological order, resolves templates,
and streams logs in real-time.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from app.orchestration.executor import LogMessage, NodeExecutor
from app.orchestration.graph_resolver import GraphResolver, ResolvedGraph

logger = logging.getLogger(__name__)


@dataclass
class PipelineExecutionContext:
    """Context for pipeline execution.

    Contains pipeline run information and accumulated outputs.
    """

    pipeline_id: str
    pipeline_run_id: str
    pipeline_params: dict[str, Any] = field(default_factory=dict)
    node_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    node_logs: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class PipelineExecutionResult:
    """Result of pipeline execution."""

    success: bool
    pipeline_id: str
    pipeline_run_id: str
    node_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    error: str | None = None


class PipelineExecutor:
    """Executes pipelines by orchestrating node execution.

    Features:
    - Topological execution order
    - Template resolution ({{ node_id.output }})
    - Real-time log streaming
    - Error handling and propagation

    Usage:
        executor = PipelineExecutor(graph_definition, params)
        async for logs, result in executor.execute_with_streaming(
            pipeline_id="...",
            pipeline_run_id="...",
        ):
            if logs:
                # Stream logs to client
                pass
            else:
                # Final result
                print(f"Pipeline completed: {result}")
    """

    def __init__(
        self,
        graph_definition: dict[str, Any],
        pipeline_params: dict[str, Any] | None = None,
    ):
        """Initialize pipeline executor.

        Args:
            graph_definition: React Flow graph state
            pipeline_params: Pipeline input parameters
        """
        self.graph_definition = graph_definition
        self.pipeline_params = pipeline_params or {}
        self.node_executor = NodeExecutor()

    async def execute(
        self,
        pipeline_id: str,
        pipeline_run_id: str,
    ) -> PipelineExecutionResult:
        """Execute pipeline without streaming.

        Args:
            pipeline_id: Pipeline UUID
            pipeline_run_id: Pipeline run UUID

        Returns:
            PipelineExecutionResult
        """
        # Collect all logs and return final result
        final_result = None
        async for logs, result in self.execute_with_streaming(
            pipeline_id, pipeline_run_id
        ):
            if result is not None:
                final_result = result

        return final_result

    async def execute_with_streaming(
        self,
        pipeline_id: str,
        pipeline_run_id: str,
    ) -> AsyncGenerator[tuple[list[LogMessage], PipelineExecutionResult | None], None]:
        """Execute pipeline with real-time log streaming.

        Args:
            pipeline_id: Pipeline UUID
            pipeline_run_id: Pipeline run UUID

        Yields:
            Tuples of (logs, result) where:
                - logs: List of LogMessage objects (empty for final result)
                - result: Final PipelineExecutionResult (None for log-only yields)
        """
        # Resolve graph
        resolver = GraphResolver(self.graph_definition)
        resolved = resolver.resolve()

        if resolved.has_cycle:
            yield (
                [],
                PipelineExecutionResult(
                    success=False,
                    pipeline_id=pipeline_id,
                    pipeline_run_id=pipeline_run_id,
                    error=resolved.error_message,
                ),
            )
            return

        # Create execution context
        context = PipelineExecutionContext(
            pipeline_id=pipeline_id,
            pipeline_run_id=pipeline_run_id,
            pipeline_params=self._extract_pipeline_params(resolved),
        )

        # Execute nodes in topological order
        node_results = {}
        try:
            for node_id in resolved.execution_order:
                async for logs, result in self._execute_node(
                    node_id=node_id,
                    resolved=resolved,
                    context=context,
                ):
                    # Stream logs
                    if logs:
                        yield logs, None
                    elif result is not None:
                        # Store node result
                        node_results[node_id] = result

            # Final result
            yield (
                [],
                PipelineExecutionResult(
                    success=True,
                    pipeline_id=pipeline_id,
                    pipeline_run_id=pipeline_run_id,
                    node_results=node_results,
                ),
            )

        except Exception as e:
            logger.exception(f"Pipeline execution failed: {e}")
            yield (
                [],
                PipelineExecutionResult(
                    success=False,
                    pipeline_id=pipeline_id,
                    pipeline_run_id=pipeline_run_id,
                    node_results=node_results,
                    error=str(e),
                ),
            )

    def _extract_pipeline_params(self, resolved: ResolvedGraph) -> dict[str, Any]:
        """Extract pipeline parameters from graph.

        Looks for PipelineParams nodes and extracts their values.

        Args:
            resolved: Resolved graph

        Returns:
            Dictionary of parameter name -> value
        """
        params = {}

        for node_data in self.graph_definition.get("nodes", []):
            if node_data.get("type") == "PipelineParams":
                node_params = node_data.get("data", {}).get("parameters", [])
                for param in node_params:
                    name = param.get("name", "")
                    default = param.get("default")
                    if name:
                        params[name] = default

        # Override with provided params
        params.update(self.pipeline_params)

        return params

    async def _execute_node(
        self,
        node_id: str,
        resolved: ResolvedGraph,
        context: PipelineExecutionContext,
    ) -> AsyncGenerator[tuple[list[LogMessage], dict[str, Any] | None], None]:
        """Execute a single node.

        Args:
            node_id: Node to execute
            resolved: Resolved graph
            context: Execution context

        Yields:
            Tuples of (logs, result)
        """
        node = resolved.nodes[node_id]
        node_data = node.data

        # Get node type
        node_type = node_data.get("type", node.node_type)

        # Resolve templates in node config
        resolved_config = self._resolve_templates(node_data, context)

        # Get upstream outputs for context
        upstream_outputs = self._get_upstream_outputs(node, context)

        # Prepare pipeline params with context
        pipeline_params = {
            **context.pipeline_params,
            "_pipeline_id": context.pipeline_id,
            "_pipeline_run_id": context.pipeline_run_id,
            "_node_id": node_id,
        }

        # Execute node with streaming
        async for logs, result in self.node_executor.execute_node_with_streaming(
            node_type=node_type,
            node_config=resolved_config,
            pipeline_params=pipeline_params,
            upstream_outputs=upstream_outputs,
            pipeline_run_id=context.pipeline_run_id,
            node_id=node_id,
        ):
            if logs:
                yield logs, None
            else:
                # Store result
                if result:
                    context.node_outputs[node_id] = result.get("outputs", {})
                    context.node_logs[node_id] = result.get("logs", [])
                    yield [], result

    def _get_upstream_outputs(
        self, node: Any, context: PipelineExecutionContext
    ) -> dict[str, dict[str, Any]]:
        """Get outputs from upstream nodes.

        Args:
            node: GraphNode
            context: Execution context

        Returns:
            Dictionary of node_id -> outputs
        """
        upstream = {}
        for dep_id in node.dependencies:
            if dep_id in context.node_outputs:
                upstream[dep_id] = context.node_outputs[dep_id]
        return upstream

    def _resolve_templates(
        self,
        node_data: dict[str, Any],
        context: PipelineExecutionContext,
    ) -> dict[str, Any]:
        """Resolve templates in node configuration.

        Replaces {{ node_id.output_name }} and {{ params.name }}
        with actual values.

        Args:
            node_data: Node data dictionary (may be nested)
            context: Execution context

        Returns:
            Node data with templates resolved
        """
        import json

        def resolve_value(value: Any) -> Any:
            if isinstance(value, str):
                return self._resolve_string_templates(value, context)
            elif isinstance(value, dict):
                return {k: resolve_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [resolve_value(item) for item in value]
            else:
                return value

        return resolve_value(node_data)

    def _resolve_string_templates(
        self,
        template: str,
        context: PipelineExecutionContext,
    ) -> str:
        """Resolve templates in a string.

        Supports:
        - {{ node_id.output_name }} - node output reference
        - {{ params.param_name }} - pipeline parameter reference

        Args:
            template: String with potential templates
            context: Execution context

        Returns:
            String with templates resolved
        """
        import re

        def replace_ref(match: re.Match) -> str:
            ref = match.group(1).strip()

            # Check for params reference
            if ref.startswith("params."):
                param_name = ref[7:]  # Remove "params." prefix
                return str(context.pipeline_params.get(param_name, match.group(0)))

            # Check for node output reference
            parts = ref.split(".", 1)
            if len(parts) == 2:
                node_id, output_name = parts
                output_value = context.node_outputs.get(node_id, {}).get(output_name)
                if output_value is not None:
                    return str(output_value)

            # No match - keep original
            return match.group(0)

        return re.sub(r"\{\{\s*(.+?)\s*\}\}", replace_ref, template)

    async def close(self) -> None:
        """Cleanup executor resources."""
        self.node_executor.shutdown(wait=False)

    async def __aenter__(self) -> "PipelineExecutor":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()


async def execute_pipeline(
    pipeline_id: str,
    pipeline_run_id: str,
    graph_definition: dict[str, Any],
    pipeline_params: dict[str, Any] | None = None,
) -> PipelineExecutionResult:
    """Execute a pipeline.

    Convenience function for simple pipeline execution.

    Args:
        pipeline_id: Pipeline UUID
        pipeline_run_id: Pipeline run UUID
        graph_definition: React Flow graph state
        pipeline_params: Pipeline input parameters

    Returns:
        PipelineExecutionResult
    """
    async with PipelineExecutor(graph_definition, pipeline_params) as executor:
        return await executor.execute(pipeline_id, pipeline_run_id)


async def execute_pipeline_with_streaming(
    pipeline_id: str,
    pipeline_run_id: str,
    graph_definition: dict[str, Any],
    pipeline_params: dict[str, Any] | None = None,
) -> AsyncGenerator[tuple[list[LogMessage], PipelineExecutionResult | None], None]:
    """Execute a pipeline with real-time log streaming.

    Convenience function for streaming execution.

    Args:
        pipeline_id: Pipeline UUID
        pipeline_run_id: Pipeline run UUID
        graph_definition: React Flow graph state
        pipeline_params: Pipeline input parameters

    Yields:
        Tuples of (logs, result)
    """
    async with PipelineExecutor(graph_definition, pipeline_params) as executor:
        async for logs, result in executor.execute_with_streaming(
            pipeline_id, pipeline_run_id
        ):
            yield logs, result
