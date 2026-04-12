"""PipelineRunner — background scheduler that executes pipelines like Airflow LocalExecutor.

This module provides:
- PipelineRunner: Background service that polls DB for pipeline runs and schedules nodes
- ProcessPoolExecutor: Each node runs in an isolated process (like Airflow LocalExecutor)
- Incremental node completion: Nodes finish individually, unblocking downstream nodes immediately
- Crash recovery: On service restart, RUNNING runs are marked as FAILED

Status transitions (uses model's RunStatus enum):
    PipelineRun: Running → Success | Failed
    NodeRun:   Pending → Running → Success | Failed
"""

import asyncio
import logging
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.core.logging_setup import setup_runner_logging
from app.models.node_run import NodeRun
from app.models.pipeline_run import PipelineRun, RunStatus
from app.models.pipeline_version import PipelineVersion

logger = logging.getLogger(__name__)

# Status constants matching model's RunStatus enum
STATUS_RUNNING = RunStatus.RUNNING.value
STATUS_SUCCESS = RunStatus.SUCCESS.value
STATUS_FAILED = RunStatus.FAILED.value
STATUS_PENDING = RunStatus.PENDING.value


# ---------------------------------------------------------------------------
# PipelineRunner
# ---------------------------------------------------------------------------


class PipelineRunner:
    """Background scheduler that polls DB and executes nodes in process pool.

    Architecture:
        ┌──────────────────────────────────────────────────────┐
        │  FastAPI App (event loop)                            │
        │                                                      │
        │  ┌──────────────┐    ┌─────────────────────────┐     │
        │  │  API Handlers│    │  PipelineRunner         │     │
        │  │              │    │  (asyncio loop каждые   │     │
        │  │ POST /run →  │    │   poll_interval)        │     │
        │  │   INSERT     │    │                         │     │
        │  │   Running    │    │  ┌────────────────────┐ │     │
        │  └──────────────┘    │  │ 1. Crash recovery  │ │     │
        │                      │  │ 2. Fetch Running   │ │     │
        │  ┌──────────────┐    │  │ 3. Schedule nodes  │ │     │
        │  │  GET /runs   │    │  │ 4. Poll completions│ │     │
        │  │  polling     │◀───│  │ 5. Update DB       │ │     │
        │  └──────────────┘    │  └────────────────────┘ │     │
        │                      └─────────────────────────┘     │
        └──────────────────────────────────────────────────────┘

    Node concurrency is controlled per-pipeline via graph_definition:
        { "settings": { "max_active_nodes": 8 }, "nodes": [...], "edges": [...] }

    The process pool has no global worker limit (defaults to os.cpu_count()).
    Each node runs in a separate process via ProcessPoolExecutor.
    Node outputs are stored in DB (NodeRun.output_values) for downstream
    template resolution.

    Usage:
        runner = PipelineRunner(max_concurrent_runs=4)
        await runner.start()  # launches background loop
        ...
        await runner.stop()   # graceful shutdown
    """

    def __init__(
        self,
        max_concurrent_runs: int | None = None,
        poll_interval: float = 2.0,
    ):
        """Initialize pipeline runner.

        Args:
            max_concurrent_runs: Max pipeline runs executing simultaneously.
                None = unlimited.
            poll_interval: Seconds between DB polling cycles.
        """
        self.max_concurrent_runs = max_concurrent_runs
        self.poll_interval = poll_interval

        # Process pool — no global limit, defaults to os.cpu_count()
        self._process_pool = ProcessPoolExecutor()

        # Active tasks: {node_run_id: (asyncio.Task, pipeline_run_id)}
        self._active_tasks: dict[str, tuple[asyncio.Task, str]] = {}

        # Engine/session for background queries (independent of API sessions)
        self._engine = create_async_engine(settings.DATABASE_URL)

        # Shutdown flag
        self._running = False
        self._background_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the background polling loop."""
        # Setup runner-specific logging (separate from FastAPI root logger)
        setup_runner_logging(log_dir=settings.LOG_DIR)
        logger.info("PipelineRunner starting...")
        # 1. Crash recovery — mark orphaned RUNNING as FAILED
        await self._recover_orphaned_runs()

        self._running = True
        self._background_task = asyncio.create_task(self._poll_loop())
        logger.info("PipelineRunner started (poll_interval=%.1fs)", self.poll_interval)

    async def stop(self) -> None:
        """Stop the background loop and wait for active tasks."""
        logger.info("PipelineRunner stopping...")
        self._running = False
        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass

        # Wait for all active node tasks to finish
        if self._active_tasks:
            logger.info(
                f"Waiting for {len(self._active_tasks)} active node(s) to finish..."
            )
            await asyncio.gather(
                *(t for t, _ in self._active_tasks.values()),
                return_exceptions=True,
            )

        self._process_pool.shutdown(wait=True)
        await self._engine.dispose()
        logger.info("PipelineRunner stopped")

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    async def _poll_loop(self) -> None:
        """Main loop: runs every poll_interval seconds."""
        logger.info("Poll loop started")
        while self._running:
            try:
                await self._tick()
            except Exception:
                logger.exception("PipelineRunner tick failed")

            await asyncio.sleep(self.poll_interval)

    async def _tick(self) -> None:
        """Single iteration of the poll loop."""
        async with AsyncSession(self._engine) as session:
            # 1. Check completed tasks and update DB
            await self._process_completed_tasks(session)

            # 2. For each Running run, schedule ready nodes
            await self._schedule_ready_nodes(session)

            await session.commit()

    # ------------------------------------------------------------------
    # Crash recovery
    # ------------------------------------------------------------------

    async def _recover_orphaned_runs(self) -> None:
        """On startup, mark RUNNING runs as FAILED (service was restarted)."""
        async with AsyncSession(self._engine) as session:
            result = await session.execute(
                select(PipelineRun).where(PipelineRun.status == STATUS_RUNNING)
            )
            orphaned = result.scalars().all()

            if orphaned:
                ids = [r.id for r in orphaned]
                logger.warning(f"Recovering {len(ids)} orphaned run(s): {ids}")

                await session.execute(
                    update(PipelineRun)
                    .where(PipelineRun.id.in_(ids))
                    .values(
                        status=STATUS_FAILED,
                        error_message="Service restarted — run was interrupted",
                        completed_at=datetime.utcnow(),
                    )
                )
                # Also fail all their node runs
                await session.execute(
                    update(NodeRun)
                    .where(NodeRun.pipeline_run_id.in_(ids))
                    .where(NodeRun.status == STATUS_RUNNING)
                    .values(
                        status=STATUS_FAILED,
                        completed_at=datetime.utcnow(),
                    )
                )
                await session.commit()

    # ------------------------------------------------------------------
    # Node scheduling
    # ------------------------------------------------------------------

    async def _schedule_ready_nodes(self, session: AsyncSession) -> None:
        """For each Running pipeline run, find nodes that are Ready and launch them."""
        # Get Running pipeline runs, oldest first (FIFO scheduling)
        stmt = (
            select(PipelineRun)
            .where(PipelineRun.status == STATUS_RUNNING)
            .order_by(PipelineRun.started_at.asc())
        )

        if self.max_concurrent_runs is not None:
            stmt = stmt.limit(self.max_concurrent_runs)

        result = await session.execute(stmt)
        running_runs = result.scalars().all()

        for pipeline_run in running_runs:
            # Explicitly load PipelineVersion (no relationship exists)
            pv_result = await session.execute(
                select(PipelineVersion).where(
                    PipelineVersion.id == pipeline_run.version_id
                )
            )
            pipeline_version = pv_result.scalar_one_or_none()
            if not pipeline_version:
                logger.error(
                    f"PipelineVersion {pipeline_run.version_id} not found for run {pipeline_run.id}"
                )
                continue

            graph = pipeline_version.graph_definition
            max_active = graph.get("settings", {}).get("max_active_nodes")

            # Count currently running nodes for this run
            running_count = await self._count_running_nodes(session, pipeline_run.id)

            # Calculate available slots
            if max_active is not None:
                slots = max_active - running_count
                if slots <= 0:
                    continue
            else:
                slots = float("inf")  # unlimited for this pipeline

            # Find nodes ready to execute
            ready_nodes = await self._find_ready_nodes(session, pipeline_run, graph)

            # Launch up to available slots
            for node in ready_nodes[
                : int(slots) if slots != float("inf") else len(ready_nodes)
            ]:
                await self._launch_node(session, pipeline_run, node, graph)

    async def _find_ready_nodes(
        self,
        session: AsyncSession,
        pipeline_run: PipelineRun,
        graph_definition: dict[str, Any],
    ) -> list[NodeRun]:
        """Find nodes whose upstream dependencies are all Success.

        A node transitions Pending → Running when every node it depends on
        has status = Success.
        """
        # Get all node runs for this pipeline run
        result = await session.execute(
            select(NodeRun)
            .where(NodeRun.pipeline_run_id == pipeline_run.id)
            .where(NodeRun.status == STATUS_PENDING)
        )
        pending_nodes = result.scalars().all()

        # Get Success node_ids
        result = await session.execute(
            select(NodeRun.node_id).where(
                NodeRun.pipeline_run_id == pipeline_run.id,
                NodeRun.status == STATUS_SUCCESS,
            )
        )
        done_node_ids = {row[0] for row in result.all()}

        # Build dependency map from graph definition (passed explicitly, no relationship)
        node_deps = self._build_dependency_map(graph_definition)

        ready = []
        for node_run in pending_nodes:
            deps = node_deps.get(node_run.node_id, [])
            if all(dep in done_node_ids for dep in deps):
                ready.append(node_run)

        return ready

    async def _launch_node(
        self,
        session: AsyncSession,
        pipeline_run: PipelineRun,
        node_run: NodeRun,
        graph_definition: dict[str, Any],
    ) -> None:
        """Transition Pending → Running and submit to process pool."""
        node_run.status = STATUS_RUNNING
        node_run.started_at = datetime.utcnow()
        await session.flush()

        # Get node config from graph_definition (not from NodeRun.output_values!)
        node_config = self._get_node_config(graph_definition, node_run.node_id)

        # Resolve connection references (UUID → BaseConnection objects) — in main process
        node_config = await self._resolve_connections(
            session, node_config, node_run.node_type
        )

        # TODO: Resolve node config with upstream outputs (dependency resolution)
        # upstream_outputs = await self._get_upstream_outputs(
        #     session, pipeline_run.id, node_run.node_id
        # )
        upstream_outputs = {}

        # Submit to process pool — runs in separate process
        loop = asyncio.get_event_loop()
        task = loop.run_in_executor(
            self._process_pool,
            self._execute_node_in_process,
            {
                "node_type": node_run.node_type,
                "node_id": node_run.node_id,
                "node_config": node_config,
                "pipeline_params": pipeline_run.parameters,
                "version_id": pipeline_run.version_id,
                "upstream_outputs": upstream_outputs,
                "pipeline_run_id": pipeline_run.id,
            },
        )

        self._active_tasks[node_run.id] = (task, pipeline_run.id)
        logger.info(
            f"Node {node_run.node_id} launched in process "
            f"(run {pipeline_run.id}, active tasks: {len(self._active_tasks)})"
        )

    # ------------------------------------------------------------------
    # Task completion processing
    # ------------------------------------------------------------------

    async def _process_completed_tasks(self, session: AsyncSession) -> None:
        """Check for finished tasks and update DB immediately."""
        completed = [
            (node_run_id, task, run_id)
            for node_run_id, (task, run_id) in self._active_tasks.items()
            if task.done()
        ]

        for node_run_id, task, pipeline_run_id in completed:
            try:
                result = task.result()

                if result.get("success"):
                    # Running → Success
                    result_stmt = (
                        update(NodeRun)
                        .where(NodeRun.id == node_run_id)
                        .values(
                            status=STATUS_SUCCESS,
                            output_values=result.get("outputs", {}),
                            completed_at=datetime.utcnow(),
                        )
                    )
                    await session.execute(result_stmt)
                    logger.info(f"Node {node_run_id} completed (Success)")
                else:
                    # Running → Failed
                    fail_stmt = (
                        update(NodeRun)
                        .where(NodeRun.id == node_run_id)
                        .values(
                            status=STATUS_FAILED,
                            completed_at=datetime.utcnow(),
                        )
                    )
                    await session.execute(fail_stmt)
                    logger.warning(f"Node {node_run_id} failed: {result.get('error')}")

            except Exception as e:
                # Process crashed
                crash_stmt = (
                    update(NodeRun)
                    .where(NodeRun.id == node_run_id)
                    .values(
                        status=STATUS_FAILED,
                        completed_at=datetime.utcnow(),
                    )
                )
                await session.execute(crash_stmt)
                logger.error(f"Node {node_run_id} crashed: {e}")

            del self._active_tasks[node_run_id]

        # Check if any pipeline runs have completed (all nodes Success or any Failed)
        await self._check_run_completion(session)

    async def _check_run_completion(self, session: AsyncSession) -> None:
        """Check if Running pipeline runs have all nodes finished."""
        result = await session.execute(
            select(PipelineRun).where(PipelineRun.status == STATUS_RUNNING)
        )
        running_runs = result.scalars().all()

        for pipeline_run in running_runs:
            # Check if any node Failed
            failed = await session.execute(
                select(NodeRun).where(
                    NodeRun.pipeline_run_id == pipeline_run.id,
                    NodeRun.status == STATUS_FAILED,
                )
            )
            if failed.scalars().first():
                # Pipeline Failed
                await session.execute(
                    update(PipelineRun)
                    .where(PipelineRun.id == pipeline_run.id)
                    .values(
                        status=STATUS_FAILED,
                        error_message="One or more nodes failed",
                        completed_at=datetime.utcnow(),
                    )
                )
                # Cancel remaining running nodes
                remaining = await session.execute(
                    select(NodeRun).where(
                        NodeRun.pipeline_run_id == pipeline_run.id,
                        NodeRun.status == STATUS_RUNNING,
                    )
                )
                for node in remaining.scalars().all():
                    # Kill task if still active
                    if node.id in self._active_tasks:
                        task, _ = self._active_tasks[node.id]
                        task.cancel()
                        del self._active_tasks[node.id]

                logger.warning(f"Pipeline run {pipeline_run.id} failed")
                continue

            # Check if all nodes Success
            all_nodes = await session.execute(
                select(NodeRun).where(NodeRun.pipeline_run_id == pipeline_run.id)
            )
            nodes = all_nodes.scalars().all()
            if not nodes:
                continue

            all_success = all(n.status == STATUS_SUCCESS for n in nodes)

            if all_success:
                # Pipeline Success
                await session.execute(
                    update(PipelineRun)
                    .where(PipelineRun.id == pipeline_run.id)
                    .values(
                        status=STATUS_SUCCESS,
                        completed_at=datetime.utcnow(),
                    )
                )
                logger.info(f"Pipeline run {pipeline_run.id} completed (Success)")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _count_running_nodes(
        self, session: AsyncSession, pipeline_run_id: str
    ) -> int:
        """Count nodes currently running for a pipeline run."""
        from sqlalchemy import func

        result = await session.execute(
            select(func.count(NodeRun.id)).where(
                NodeRun.pipeline_run_id == pipeline_run_id,
                NodeRun.status == STATUS_RUNNING,
            )
        )
        return result.scalar() or 0

    async def _get_upstream_outputs(
        self, session: AsyncSession, pipeline_run_id: str, node_id: str
    ) -> dict[str, dict[str, Any]]:
        """Get outputs from upstream Success nodes for template resolution."""
        from app.orchestration.graph_resolver import GraphResolver

        # Explicitly load pipeline version to get graph
        run_result = await session.execute(
            select(PipelineRun).where(PipelineRun.id == pipeline_run_id)
        )
        pipeline_run = run_result.scalar_one()

        pv_result = await session.execute(
            select(PipelineVersion).where(PipelineVersion.id == pipeline_run.version_id)
        )
        pipeline_version = pv_result.scalar_one()

        graph_def = pipeline_version.graph_definition
        resolver = GraphResolver(graph_def)
        resolved = resolver.resolve()

        # Get upstream node_ids
        graph_node = resolved.nodes.get(node_id)
        if not graph_node:
            return {}

        upstream_ids = [dep for dep in graph_node.dependencies]

        # Get outputs from Success nodes
        result = await session.execute(
            select(NodeRun).where(
                NodeRun.pipeline_run_id == pipeline_run_id,
                NodeRun.node_id.in_(upstream_ids),
                NodeRun.status == STATUS_SUCCESS,
            )
        )
        done_nodes = result.scalars().all()

        return {n.node_id: n.output_values for n in done_nodes}

    @staticmethod
    def _get_node_config(
        graph_definition: dict[str, Any], node_id: str
    ) -> dict[str, Any]:
        """Extract node config from graph_definition.

        Config is stored under nodes[].data.config in the graph_definition.
        """
        for node in graph_definition.get("nodes", []):
            if node.get("id") == node_id:
                return node.get("data", {}).get("config", {})
        return {}

    @staticmethod
    async def _resolve_connections(
        session: AsyncSession, config: dict[str, Any], node_type: str
    ) -> dict[str, Any]:
        """Replace UUID connection references with full connection objects.

        Uses the provided session (no new engine needed).
        Batch-fetches all connections in a single query.
        """
        import uuid

        from sqlalchemy import select

        from app.models.connection import Connection
        from app.nodes.registry import NodeRegistry
        from app.schemas.connection import BaseConnection, assemble_connection

        # Ensure registry is populated
        if not NodeRegistry.list_types():
            NodeRegistry.scan_nodes()

        if not NodeRegistry.is_registered(node_type):
            return config

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
            return config

        # Collect all valid UUID connection IDs
        connection_ids = []
        field_to_id: dict[str, str] = {}
        for field_name in connection_field_names:
            value = config.get(field_name)
            if not isinstance(value, str):
                continue
            try:
                uuid.UUID(value)
            except ValueError:
                continue
            connection_ids.append(value)
            field_to_id[field_name] = value

        if not connection_ids:
            return config

        # Single batch query
        result = await session.execute(
            select(Connection).where(Connection.id.in_(connection_ids))
        )
        connections = result.scalars().all()
        conn_map = {c.id: c for c in connections}

        # Resolve
        resolved = dict(config)
        for field_name, conn_id in field_to_id.items():
            db_conn = conn_map.get(conn_id)
            if db_conn:
                resolved[field_name] = assemble_connection(
                    db_conn.connection_type.value,
                    db_conn.config,
                    db_conn.secrets,
                )

        return resolved

    @staticmethod
    def _build_dependency_map(graph_def: dict[str, Any]) -> dict[str, list[str]]:
        """Build node_id → [dependency_node_ids] map from graph definition."""
        deps: dict[str, list[str]] = {n["id"]: [] for n in graph_def.get("nodes", [])}
        for edge in graph_def.get("edges", []):
            target = edge.get("target")
            source = edge.get("source")
            if target and source:
                deps[target].append(source)
        return deps

    # ------------------------------------------------------------------
    # Subprocess logging helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _isolate_logging() -> None:
        """Close all inherited logging handlers in a forked child.

        ProcessPoolExecutor forks the child from the parent, inheriting all
        logging handlers (server.log, runner.log, etc.).  Those handlers
        have their own open() file descriptors that bypass os.dup2, so node
        output would leak into server.log.  Close everything first.
        """
        root = logging.getLogger()
        for handler in list(root.handlers):
            try:
                handler.close()
            except Exception:
                pass
        root.handlers.clear()
        root.setLevel(logging.WARNING)

        for name in list(logging.Logger.manager.loggerDict):
            lg = logging.getLogger(name)
            for handler in list(lg.handlers):
                try:
                    handler.close()
                except Exception:
                    pass
            lg.handlers.clear()
            lg.propagate = False

    @staticmethod
    def _resolve_node_log_path(
        version_id: str, node_id: str, pipeline_run_id: str
    ) -> Path:
        """Build the log file path: LOG_DIR/run_logs/<version_id>/<node_id>/<run_id>.log."""
        log_dir = Path(settings.LOG_DIR) / "run_logs" / version_id / node_id
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / f"{pipeline_run_id}.log"

    class _LogRedirect:
        """Context manager that redirects stdout/stderr to a file via os.dup2.

        Works at the OS level (fd 1 and fd 2), capturing everything:
        python print(), subprocess output, logging module output, etc.

        In a forked subprocess there is no need to restore sys.stdout/stderr —
        the process exits after returning a dict, so we just flush and close.
        """

        __slots__ = (
            "log_file",
            "_stdout_fd",
            "_stderr_fd",
            "_orig_stdout",
            "_orig_stderr",
            "log_f",
        )

        def __init__(self, log_file: Path) -> None:
            self.log_file = log_file
            self._stdout_fd = sys.stdout.fileno()
            self._stderr_fd = sys.stderr.fileno()
            self._orig_stdout: int | None = None
            self._orig_stderr: int | None = None

        def __enter__(self) -> "_LogRedirect":
            # Save original file descriptors
            self._orig_stdout = os.dup(self._stdout_fd)
            self._orig_stderr = os.dup(self._stderr_fd)

            # Open log file and redirect fd 1 and fd 2
            self.log_f = open(self.log_file, "w", encoding="utf-8")
            os.dup2(self.log_f.fileno(), self._stdout_fd)
            os.dup2(self.log_f.fileno(), self._stderr_fd)

            # Also redirect Python-level stdout/stderr to the log file
            # so that logger.StreamHandler(sys.stdout) writes to it too.
            # IMPORTANT: closefd=False — the wrapper must NOT own fd 1/2.
            # Without it, GC of the old sys.stdout closes fd 1 (which now
            # points to the log file), causing [Errno 9] on multiprocess
            # return-value serialization.
            sys.stdout = open(self._stdout_fd, "w", closefd=False)
            sys.stderr = open(self._stderr_fd, "w", closefd=False)

            return self

        def __exit__(self, *args: Any) -> None:
            # Flush any pending output to the log file
            sys.stdout.flush()
            sys.stderr.flush()

            # Close the log file — fd 1/2 are still valid because
            # closefd=False above, so they were never "owned" by Python.
            self.log_f.close()

    # ------------------------------------------------------------------
    # Node execution entry point
    # ------------------------------------------------------------------

    @staticmethod
    def _execute_node_in_process(spec: dict[str, Any]) -> dict[str, Any]:
        """Execute a node in a separate process.

        Connections are already resolved in the main process before submission.
        node_config is cast directly to the InputSchema type.

        Args:
            spec: Dict with node_type, node_id, node_config, pipeline_params,
                  upstream_outputs, pipeline_run_id

        Returns:
            Dict with success, outputs, logs, error keys
        """
        # 1. Logging isolation
        PipelineRunner._isolate_logging()

        # 2. Resolve log path and redirect output FIRST — so ALL errors
        #    (including node load failures) are captured in the log file
        log_file = PipelineRunner._resolve_node_log_path(
            version_id=spec["version_id"],
            node_id=spec["node_id"],
            pipeline_run_id=spec["pipeline_run_id"],
        )

        with PipelineRunner._LogRedirect(log_file):
            # 3. Always re-scan nodes from disk — the parent process may have
            #    a stale registry if new node files were added while the service
            #    is running.  scan_nodes() clears its registry first, so this
            #    is safe to call unconditionally.
            from app.nodes.registry import NodeRegistry

            NodeRegistry.scan_nodes()

            try:
                node = NodeRegistry.create(spec["node_type"])
            except KeyError as e:
                print(str(e))
                return {
                    "success": False,
                    "outputs": {},
                    "logs": [],
                    "error": str(e),
                }

            if node.input_schema is None:
                err = f"Node '{spec['node_type']}' does not define input_schema"
                print(err)
                return {
                    "success": False,
                    "outputs": {},
                    "logs": [],
                    "error": err,
                }

            # 4. Run node logic
            return PipelineRunner._run_node_with_logging(spec, node)

    @staticmethod
    def _run_node_with_logging(spec: dict[str, Any], node) -> dict[str, Any]:
        """Execute node logic with proper logging.

        NOTE: By the time this runs, stdout has been redirected to the log file
        by _LogRedirect (os.dup2).  Adding a StreamHandler(sys.stdout) sends
        logging output into the same file.
        """
        # Create a real logger for the subprocess
        node_logger = logging.getLogger(f"node.{spec['node_id']}")
        node_logger.setLevel(logging.DEBUG)

        # StreamHandler writes to sys.stdout — which _LogRedirect already
        # redirected to the node's log file via os.dup2
        file_handler = logging.StreamHandler(sys.stdout)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        node_logger.addHandler(file_handler)

        try:
            inputs = node.input_schema.model_validate(spec["node_config"])
            output = node.execute(inputs, logger=node_logger)

            if node.output_schema is None:
                return {
                    "success": False,
                    "outputs": {},
                    "logs": [],
                    "error": f"Node '{spec['node_type']}' does not define output_schema",
                }

            if not isinstance(output, node.output_schema):
                raise ValueError(
                    f"Node returned {type(output).__name__}, "
                    f"expected {node.output_schema.__name__}"
                )

            return {
                "success": True,
                "outputs": output.model_dump(),
                "logs": [],
                "error": None,
            }

        except Exception as e:
            # Print full traceback to stdout (redirected to log file by
            # _LogRedirect) so the error is captured in the node's log
            import traceback

            print(f"EXCEPTION in node {spec['node_id']}:")
            traceback.print_exc()
            return {
                "success": False,
                "outputs": {},
                "logs": [],
                "error": str(e),
            }


# ---------------------------------------------------------------------------
# Singleton for lifespan integration
# ---------------------------------------------------------------------------

_runner: PipelineRunner | None = None


def get_runner() -> PipelineRunner:
    """Get or create the singleton PipelineRunner."""
    global _runner
    if _runner is None:
        _runner = PipelineRunner()
    return _runner
