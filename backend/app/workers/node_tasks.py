"""Celery tasks for node execution."""

from typing import Any

from app.nodes.base import NodeContext, NodeResult
from app.nodes.registry import NodeRegistry
from app.workers.celery_app import celery_app


@celery_app.task(bind=True)
def execute_node_task(
    self,
    pipeline_id: str,
    pipeline_run_id: str,
    node_id: str,
    node_type: str,
    node_config: dict[str, Any],
    pipeline_params: dict[str, Any],
    upstream_outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Execute a single node as a Celery task.

    This is the main entry point for node execution. Each node runs as an
    isolated Celery task with its own context and resources.

    Args:
        pipeline_id: UUID of the pipeline
        pipeline_run_id: UUID of the pipeline run
        node_id: UUID of the node within the pipeline
        node_type: Type of node to execute (e.g., "text_output")
        node_config: Node-specific configuration from the graph definition
        pipeline_params: Pipeline-level input parameters
        upstream_outputs: Outputs from upstream nodes in format:
            {"node_id": {"output_name": value, ...}, ...}

    Returns:
        Dictionary with execution result containing:
            - success: bool
            - outputs: dict of node outputs
            - logs: list of log messages
            - error: error message if failed
    """
    try:
        # Create node instance
        node = NodeRegistry.create(node_type)

        # Validate node configuration
        node.validate_config(node_config)

        # Build execution context
        context = NodeContext(
            pipeline_id=pipeline_id,
            pipeline_run_id=pipeline_run_id,
            node_id=node_id,
            pipeline_params={**pipeline_params, "node_config": node_config},
            upstream_outputs=upstream_outputs,
        )

        # Execute node with logger
        result = node.execute(context, logger=logging.getLogger(f"node.{node_id}"))

        # Return serialized result
        return {
            "success": result.success,
            "outputs": result.outputs,
            "logs": result.logs,
            "error": result.error,
        }

    except KeyError as e:
        # Node type not registered
        error_msg = f"Unknown node type: {node_type}"
        return {
            "success": False,
            "outputs": {},
            "logs": [f"Error: {error_msg}"],
            "error": error_msg,
        }

    except ValueError as e:
        # Configuration validation error
        error_msg = f"Configuration validation failed: {str(e)}"
        return {
            "success": False,
            "outputs": {},
            "logs": [f"Error: {error_msg}"],
            "error": error_msg,
        }

    except Exception as e:
        # Unexpected error
        error_msg = f"Unexpected error: {str(e)}"
        return {
            "success": False,
            "outputs": {},
            "logs": [f"Error: {error_msg}"],
            "error": error_msg,
        }


def execute_node_sync(
    node_type: str,
    node_config: dict[str, Any],
    pipeline_params: dict[str, Any],
    upstream_outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Execute a node synchronously without Celery.

    This function is used for testing and local execution.
    It runs the node in the current process (not isolated).

    For isolated execution, use app.orchestration.executor.execute_node_local.

    Args:
        node_type: Type of node to execute
        node_config: Node configuration
        pipeline_params: Pipeline parameters
        upstream_outputs: Upstream node outputs

    Returns:
        Execution result dictionary
    """
    # Add node_config to pipeline_params for compatibility
    full_params = {**pipeline_params, "node_config": node_config}

    # Create context
    context = NodeContext(
        pipeline_id=full_params.get("_pipeline_id", ""),
        pipeline_run_id=full_params.get("_pipeline_run_id", ""),
        node_id=full_params.get("_node_id", ""),
        pipeline_params=full_params,
        upstream_outputs=upstream_outputs,
    )

    try:
        # Create and validate node
        node = NodeRegistry.create(node_type)
        node.validate_config(node_config)

        # Execute with logger
        result = node.execute(context, logger=logging.getLogger(f"node.{node_id}"))

        return {
            "success": result.success,
            "outputs": result.outputs,
            "logs": result.logs,
            "error": result.error,
        }

    except KeyError as e:
        error_msg = f"Unknown node type: {node_type}"
        return {
            "success": False,
            "outputs": {},
            "logs": [f"Error: {error_msg}"],
            "error": error_msg,
        }

    except ValueError as e:
        error_msg = f"Configuration validation failed: {str(e)}"
        return {
            "success": False,
            "outputs": {},
            "logs": [f"Error: {error_msg}"],
            "error": error_msg,
        }

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        return {
            "success": False,
            "outputs": {},
            "logs": [f"Error: {error_msg}"],
            "error": error_msg,
        }
