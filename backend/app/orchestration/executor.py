"""Local node executor using ProcessPoolExecutor (like Airflow LocalExecutor).

This module provides a Celery-free way to execute nodes in isolated processes.
Useful for testing and single-machine deployments.

Supports real-time log streaming via multiprocessing.Queue.
"""

import asyncio
import logging
import multiprocessing as mp
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from multiprocessing import Queue
from typing import Any, AsyncGenerator, Optional

from app.core.config import settings
from app.orchestration.logger import create_streaming_logger

logger = logging.getLogger(__name__)


def _resolve_connections(
    config: dict[str, Any],
    node_type: str,
) -> dict[str, Any]:
    """Replace UUID connection references with full connection objects.

    Looks up the node class to find which fields expect connections,
    then fetches those connections from DB and assembles them.

    Args:
        config: Node config dict (may contain UUID strings for connection fields)
        node_type: Node type string to look up input_schema

    Returns:
        Config dict with connection references resolved to typed objects
    """
    import asyncio
    import uuid

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core.config import settings
    from app.models.connection import Connection
    from app.nodes.registry import NodeRegistry
    from app.schemas.connection import BaseConnection, assemble_connection

    # Ensure registry is populated
    if not NodeRegistry._registry:
        NodeRegistry.scan_nodes()

    if not NodeRegistry.is_registered(node_type):
        return config  # Unknown node type, return as-is

    node_class = NodeRegistry.get(node_type)
    if not node_class.input_schema:
        return config

    # Find connection fields
    connection_field_names = set()
    for field_name, field_info in node_class.input_schema.model_fields.items():
        try:
            if issubclass(field_info.annotation, BaseConnection):
                connection_field_names.add(field_name)
        except TypeError:
            pass

    if not connection_field_names:
        return config  # No connection fields

    # Resolve connections from DB
    async def _fetch_connection(conn_id: str):
        engine = create_async_engine(settings.DATABASE_URL)
        try:
            async with engine.begin() as conn:
                result = await conn.execute(
                    select(Connection).where(Connection.id == conn_id)
                )
                return result.scalar_one_or_none()
        finally:
            await engine.dispose()

    resolved = dict(config)
    for field_name in connection_field_names:
        value = config.get(field_name)
        if not isinstance(value, str):
            continue
        try:
            uuid.UUID(value)  # Validate UUID format
        except ValueError:
            continue  # Not a UUID, skip

        db_conn = asyncio.run(_fetch_connection(value))
        if db_conn:
            resolved[field_name] = assemble_connection(
                db_conn.connection_type.value,
                db_conn.config,
                db_conn.secrets,
            )

    return resolved


@dataclass
class LogMessage:
    """A log message from node execution."""

    pipeline_run_id: str
    node_id: str
    message: str
    level: str = "INFO"


def _execute_node_in_process(
    node_type: str,
    node_config: dict[str, Any],
    pipeline_params: dict[str, Any],
    upstream_outputs: dict[str, dict[str, Any]],
    log_queue: Optional[Queue] = None,
    pipeline_run_id: str = "",
    node_id: str = "",
) -> dict[str, Any]:
    """Execute a node in a separate process with optional log streaming.

    This function is called inside the process pool. It imports the node
    registry and executes the node with typed input/output schemas.

    Note: Validation and context assembly will be handled by Scheduler later.
    Currently, this function validates inputs against input_schema for safety.

    Args:
        node_type: Type of node to execute
        node_config: Node configuration (will be validated against input_schema)
        pipeline_params: Pipeline parameters
        upstream_outputs: Outputs from upstream nodes (for future Scheduler use)
        log_queue: Optional queue for streaming logs
        pipeline_run_id: Pipeline run ID for log context
        node_id: Node ID for log context

    Returns:
        Dictionary with execution result
    """
    from app.nodes.registry import NodeRegistry

    # Setup file-based logging for this node
    log_dir = os.path.join(settings.LOG_DIR, pipeline_run_id)
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{node_id}.log")

    # Create logger with both callback (for streaming) and file handler
    def on_log(message: str) -> None:
        if log_queue is not None:
            log_queue.put(
                LogMessage(
                    pipeline_run_id=pipeline_run_id,
                    node_id=node_id,
                    message=message,
                    level="INFO",
                )
            )
        # Also write to file
        with open(log_file, "a") as f:
            f.write(message + "\n")

    py_logger = create_streaming_logger(f"node.{node_id}", on_log)

    try:
        # Create node instance
        # Scan nodes in case registry is empty (fresh subprocess)
        if not NodeRegistry.list_types():
            NodeRegistry.scan_nodes()

        node = NodeRegistry.create(node_type)

        # Resolve Jinja2 templates in node_config
        # TODO: Move to Scheduler when implemented
        from app.core.template_resolver import resolve_dict_values

        resolved_config = resolve_dict_values(
            node_config,
            params=pipeline_params,
            upstream_outputs=upstream_outputs,
        )

        # Resolve connection references: replace UUID strings with full connection objects
        # TODO: Move to Scheduler when implemented
        resolved_config = _resolve_connections(resolved_config, node_type)

        # Validate configuration against input_schema
        # TODO: Move to Scheduler when implemented
        if node.input_schema is None:
            raise RuntimeError(f"Node '{node_type}' does not define input_schema")

        inputs = node.input_schema(**resolved_config)

        # Execute node with typed inputs
        output = node.execute(inputs, logger=py_logger)

        # Validate output against output_schema
        # TODO: Move to Scheduler when implemented
        if node.output_schema is None:
            raise RuntimeError(f"Node '{node_type}' does not define output_schema")

        if not isinstance(output, node.output_schema):
            raise ValueError(
                f"Node '{node_type}' returned {type(output).__name__}, "
                f"expected {node.output_schema.__name__}"
            )

        output_dict = output.model_dump()

        return {
            "success": True,
            "outputs": output_dict,
            "logs": [],  # Logs are streamed separately
            "error": None,
        }

    except KeyError as e:
        error_msg = f"Unknown node type: {node_type}"
        if log_queue:
            log_queue.put(
                LogMessage(
                    pipeline_run_id=pipeline_run_id,
                    node_id=node_id,
                    message=error_msg,
                    level="ERROR",
                )
            )
        return {
            "success": False,
            "outputs": {},
            "logs": [f"Error: {error_msg}"],
            "error": error_msg,
        }

    except ValueError as e:
        error_msg = f"Configuration validation failed: {str(e)}"
        if log_queue:
            log_queue.put(
                LogMessage(
                    pipeline_run_id=pipeline_run_id,
                    node_id=node_id,
                    message=error_msg,
                    level="ERROR",
                )
            )
        return {
            "success": False,
            "outputs": {},
            "logs": [f"Error: {error_msg}"],
            "error": error_msg,
        }

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        if log_queue:
            log_queue.put(
                LogMessage(
                    pipeline_run_id=pipeline_run_id,
                    node_id=node_id,
                    message=error_msg,
                    level="ERROR",
                )
            )
        return {
            "success": False,
            "outputs": {},
            "logs": [f"Error: {error_msg}"],
            "error": error_msg,
        }


class NodeExecutor:
    """Executes nodes in isolated processes with optional log streaming.

    Similar to Airflow's LocalExecutor, this runs tasks in a process pool
    without requiring Celery infrastructure.

    Usage:
        async with NodeExecutor(max_workers=4) as executor:
            # Simple execution
            result = await executor.execute_node(...)

            # Or with streaming
            async for logs, result in executor.execute_node_with_streaming(...):
                if logs:
                    print(f"Logs: {logs}")
                else:
                    print(f"Result: {result}")
    """

    def __init__(self, max_workers: int = 4):
        """Initialize the executor.

        Args:
            max_workers: Maximum number of concurrent worker processes
        """
        self.max_workers = max_workers
        self._executor: ProcessPoolExecutor | None = None

    def _get_executor(self) -> ProcessPoolExecutor:
        """Get or create the process pool executor."""
        if self._executor is None:
            self._executor = ProcessPoolExecutor(max_workers=self.max_workers)
        return self._executor

    async def execute_node(
        self,
        node_type: str,
        node_config: dict[str, Any],
        pipeline_params: dict[str, Any],
        upstream_outputs: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Execute a node in a separate process without streaming.

        Args:
            node_type: Type of node to execute
            node_config: Node-specific configuration
            pipeline_params: Pipeline-level parameters
            upstream_outputs: Outputs from upstream nodes

        Returns:
            Dictionary with execution result
        """
        loop = asyncio.get_event_loop()
        executor = self._get_executor()

        future = loop.run_in_executor(
            executor,
            _execute_node_in_process,
            node_type,
            node_config,
            pipeline_params,
            upstream_outputs,
            None,
            "",
            "",
        )

        return await future

    async def execute_node_with_streaming(
        self,
        node_type: str,
        node_config: dict[str, Any],
        pipeline_params: dict[str, Any],
        upstream_outputs: dict[str, dict[str, Any]],
        pipeline_run_id: str = "",
        node_id: str = "",
    ) -> AsyncGenerator[tuple[list[LogMessage], dict[str, Any] | None], None]:
        """Execute a node with real-time log streaming.

        Yields log messages as they are produced, then yields the final result.

        Args:
            node_type: Type of node to execute
            node_config: Node configuration
            pipeline_params: Pipeline parameters
            upstream_outputs: Upstream node outputs
            pipeline_run_id: Pipeline run ID for log context
            node_id: Node ID for log context

        Yields:
            Tuples of (logs, result) where:
                - logs: List of LogMessage objects (empty for final result yield)
                - result: Final execution result (None for log-only yields)
        """
        # Create manager and queue for log streaming
        manager = mp.Manager()
        log_queue = manager.Queue()

        loop = asyncio.get_event_loop()
        executor = self._get_executor()

        future = loop.run_in_executor(
            executor,
            _execute_node_in_process,
            node_type,
            node_config,
            pipeline_params,
            upstream_outputs,
            log_queue,
            pipeline_run_id,
            node_id,
        )

        collected_logs: list[LogMessage] = []

        # Poll for logs while task is running
        while not future.done():
            while not log_queue.empty():
                log_msg = log_queue.get_nowait()
                collected_logs.append(log_msg)
                yield [log_msg], None

            await asyncio.sleep(0.05)

        # Get final result
        result = await future

        # Drain any remaining logs
        while not log_queue.empty():
            log_msg = log_queue.get_nowait()
            collected_logs.append(log_msg)
            yield [log_msg], None

        # Yield final result (with empty logs list to signal completion)
        yield [], result

        # Cleanup
        manager.shutdown()

    async def execute_nodes(
        self,
        nodes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Execute multiple nodes concurrently.

        Args:
            nodes: List of node execution specs

        Returns:
            List of execution results
        """
        tasks = [
            self.execute_node(
                node_type=node["node_type"],
                node_config=node["node_config"],
                pipeline_params=node["pipeline_params"],
                upstream_outputs=node["upstream_outputs"],
            )
            for node in nodes
        ]

        return await asyncio.gather(*tasks)

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the executor."""
        if self._executor is not None:
            self._executor.shutdown(wait=wait)
            self._executor = None

    async def __aenter__(self) -> "NodeExecutor":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        self.shutdown(wait=True)


_default_executor: NodeExecutor | None = None


def get_default_executor(max_workers: int = 4) -> NodeExecutor:
    """Get or create the default executor."""
    global _default_executor
    if _default_executor is None:
        _default_executor = NodeExecutor(max_workers=max_workers)
    return _default_executor


async def execute_node_local(
    node_type: str,
    node_config: dict[str, Any],
    pipeline_params: dict[str, Any],
    upstream_outputs: dict[str, dict[str, Any]],
    max_workers: int = 4,
) -> dict[str, Any]:
    """Execute a node locally without Celery."""
    executor = get_default_executor(max_workers=max_workers)
    return await executor.execute_node(
        node_type=node_type,
        node_config=node_config,
        pipeline_params=pipeline_params,
        upstream_outputs=upstream_outputs,
    )


async def execute_node_with_streaming(
    node_type: str,
    node_config: dict[str, Any],
    pipeline_params: dict[str, Any],
    upstream_outputs: dict[str, dict[str, Any]],
    pipeline_run_id: str = "",
    node_id: str = "",
    max_workers: int = 4,
) -> AsyncGenerator[tuple[list[LogMessage], dict[str, Any] | None], None]:
    """Execute a node with real-time log streaming."""
    executor = get_default_executor(max_workers=max_workers)
    async for logs, result in executor.execute_node_with_streaming(
        node_type=node_type,
        node_config=node_config,
        pipeline_params=pipeline_params,
        upstream_outputs=upstream_outputs,
        pipeline_run_id=pipeline_run_id,
        node_id=node_id,
    ):
        yield logs, result
