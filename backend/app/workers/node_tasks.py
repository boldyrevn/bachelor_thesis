"""Celery tasks for node execution.

Note: This module will be refactored when Scheduler is implemented.
Currently handles validation and execution with typed schemas.
"""

import logging
from typing import Any

from app.nodes.registry import NodeRegistry
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


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

    Note: Validation and context assembly will move to Scheduler later.

    Args:
        pipeline_id: UUID of the pipeline
        pipeline_run_id: UUID of the pipeline run
        node_id: UUID of the node within the pipeline
        node_type: Type of node to execute (e.g., "text_output")
        node_config: Node-specific configuration from the graph definition
        pipeline_params: Pipeline-level input parameters
        upstream_outputs: Outputs from upstream nodes (for future Scheduler use)

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

        # Validate configuration against input_schema
        # TODO: Move to Scheduler when implemented
        if node.input_schema is None:
            raise RuntimeError(f"Node '{node_type}' does not define input_schema")

        inputs = node.input_schema(**node_config)

        # Execute node with logger
        # TODO: Update when Scheduler provides context
        output = node.execute(inputs, logger=logging.getLogger(f"node.{node_id}"))

        # Validate output against output_schema
        # TODO: Move to Scheduler when implemented
        if node.output_schema is None:
            raise RuntimeError(f"Node '{node_type}' does not define output_schema")

        if not isinstance(output, node.output_schema):
            raise ValueError(
                f"Node '{node_type}' returned {type(output).__name__}, "
                f"expected {node.output_schema.__name__}"
            )

        # Return serialized result
        return {
            "success": True,
            "outputs": output.model_dump(),
            "logs": [],
            "error": None,
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

    Note: Will be replaced by Scheduler when implemented.

    Args:
        node_type: Type of node to execute
        node_config: Node configuration
        pipeline_params: Pipeline parameters
        upstream_outputs: Upstream node outputs

    Returns:
        Execution result dictionary
    """
    try:
        # Create node instance
        node = NodeRegistry.create(node_type)

        # Validate configuration against input_schema
        if node.input_schema is None:
            raise RuntimeError(f"Node '{node_type}' does not define input_schema")

        inputs = node.input_schema(**node_config)

        # Execute node with logger
        node_id = pipeline_params.get("_node_id", "sync")
        output = node.execute(inputs, logger=logging.getLogger(f"node.{node_id}"))

        # Validate output against output_schema
        if node.output_schema is None:
            raise RuntimeError(f"Node '{node_type}' does not define output_schema")

        if not isinstance(output, node.output_schema):
            raise ValueError(
                f"Node '{node_type}' returned {type(output).__name__}, "
                f"expected {node.output_schema.__name__}"
            )

        return {
            "success": True,
            "outputs": output.model_dump(),
            "logs": [],
            "error": None,
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
