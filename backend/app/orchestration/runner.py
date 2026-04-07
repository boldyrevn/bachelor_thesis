"""PipelineRunner — background scheduler that executes pipelines like Airflow LocalExecutor.

This module provides:
- PipelineRunner: Background service that polls DB for pipeline runs and schedules nodes
- ProcessPoolExecutor: Each node runs in an isolated process (like Airflow LocalExecutor)
- Incremental node completion: Nodes finish individually, unblocking downstream nodes immediately
- Crash recovery: On service restart, RUNNING runs are marked as FAILED

Status transitions:
    PipelineRun: Running → Done | Failed
    NodeRun:   Pending → Ready → Running → Done | Failed
"""

import asyncio
import logging
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.models.node_run import NodeRun
from app.models.pipeline_run import PipelineRun
from app.models.pipeline_version import PipelineVersion

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Status enums (new scheme)
# ---------------------------------------------------------------------------


class PipelineRunStatus(str):
    """Pipeline run has only 2 states: active or terminal."""

    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class NodeRunStatus(str):
    """Node run transitions: Pending → Ready → Running → Done | Failed."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


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
        # 1. Crash recovery — mark orphaned RUNNING as FAILED
        await self._recover_orphaned_runs()

        self._running = True
        self._background_task = asyncio.create_task(self._poll_loop())
        logger.info("PipelineRunner started")

    async def stop(self) -> None:
        """Stop the background loop and wait for active tasks."""
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
                select(PipelineRun).where(
                    PipelineRun.status == PipelineRunStatus.RUNNING
                )
            )
            orphaned = result.scalars().all()

            if orphaned:
                ids = [r.id for r in orphaned]
                logger.warning(f"Recovering {len(ids)} orphaned run(s): {ids}")

                await session.execute(
                    update(PipelineRun)
                    .where(PipelineRun.id.in_(ids))
                    .values(
                        status=PipelineRunStatus.FAILED,
                        error_message="Service restarted — run was interrupted",
                        completed_at=datetime.utcnow(),
                    )
                )
                # Also fail all their node runs
                await session.execute(
                    update(NodeRun)
                    .where(NodeRun.pipeline_run_id.in_(ids))
                    .where(NodeRun.status == NodeRunStatus.RUNNING)
                    .values(
                        status=NodeRunStatus.FAILED,
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
            .where(PipelineRun.status == PipelineRunStatus.RUNNING)
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
        """Find nodes whose upstream dependencies are all Done.

        A node transitions Pending → Ready when every node it depends on
        has status = Done.
        """
        # Get all node runs for this pipeline run
        result = await session.execute(
            select(NodeRun)
            .where(NodeRun.pipeline_run_id == pipeline_run.id)
            .where(NodeRun.status == NodeRunStatus.PENDING)
        )
        pending_nodes = result.scalars().all()

        # Get Done node_ids
        result = await session.execute(
            select(NodeRun.node_id).where(
                NodeRun.pipeline_run_id == pipeline_run.id,
                NodeRun.status == NodeRunStatus.DONE,
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
        """Transition Pending → Ready → Running and submit to process pool."""
        # Pending → Ready → Running (atomic transition)
        node_run.status = NodeRunStatus.RUNNING
        node_run.started_at = datetime.utcnow()
        await session.flush()

        # Get node config from graph_definition (not from NodeRun.output_values!)
        node_config = self._get_node_config(graph_definition, node_run.node_id)

        # Resolve node config with upstream outputs
        upstream_outputs = await self._get_upstream_outputs(
            session, pipeline_run.id, node_run.node_id
        )

        # Resolve connection references (UUID → BaseConnection objects) — in main process
        node_config = await self._resolve_connections(
            session, node_config, node_run.node_type
        )

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
                    # Running → Done
                    result_stmt = (
                        update(NodeRun)
                        .where(NodeRun.id == node_run_id)
                        .values(
                            status=NodeRunStatus.DONE,
                            output_values=result.get("outputs", {}),
                            completed_at=datetime.utcnow(),
                        )
                    )
                    await session.execute(result_stmt)
                    logger.info(f"Node {node_run_id} completed (Done)")
                else:
                    # Running → Failed
                    fail_stmt = (
                        update(NodeRun)
                        .where(NodeRun.id == node_run_id)
                        .values(
                            status=NodeRunStatus.FAILED,
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
                        status=NodeRunStatus.FAILED,
                        completed_at=datetime.utcnow(),
                    )
                )
                await session.execute(crash_stmt)
                logger.error(f"Node {node_run_id} crashed: {e}")

            del self._active_tasks[node_run_id]

        # Check if any pipeline runs have completed (all nodes Done or any Failed)
        await self._check_run_completion(session)

    async def _check_run_completion(self, session: AsyncSession) -> None:
        """Check if Running pipeline runs have all nodes finished."""
        result = await session.execute(
            select(PipelineRun).where(PipelineRun.status == PipelineRunStatus.RUNNING)
        )
        running_runs = result.scalars().all()

        for pipeline_run in running_runs:
            # Check if any node Failed
            failed = await session.execute(
                select(NodeRun).where(
                    NodeRun.pipeline_run_id == pipeline_run.id,
                    NodeRun.status == NodeRunStatus.FAILED,
                )
            )
            if failed.scalars().first():
                # Pipeline Failed
                await session.execute(
                    update(PipelineRun)
                    .where(PipelineRun.id == pipeline_run.id)
                    .values(
                        status=PipelineRunStatus.FAILED,
                        error_message="One or more nodes failed",
                        completed_at=datetime.utcnow(),
                    )
                )
                # Cancel remaining running nodes
                remaining = await session.execute(
                    select(NodeRun).where(
                        NodeRun.pipeline_run_id == pipeline_run.id,
                        NodeRun.status == NodeRunStatus.RUNNING,
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

            # Check if all nodes Done
            all_nodes = await session.execute(
                select(NodeRun).where(NodeRun.pipeline_run_id == pipeline_run.id)
            )
            nodes = all_nodes.scalars().all()
            if not nodes:
                continue

            all_done = all(n.status == NodeRunStatus.DONE for n in nodes)
            any_terminal = all(
                n.status in (NodeRunStatus.DONE, NodeRunStatus.FAILED) for n in nodes
            )

            if any_terminal:
                # Pipeline Done
                await session.execute(
                    update(PipelineRun)
                    .where(PipelineRun.id == pipeline_run.id)
                    .values(
                        status=PipelineRunStatus.DONE,
                        completed_at=datetime.utcnow(),
                    )
                )
                logger.info(f"Pipeline run {pipeline_run.id} completed (Done)")

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
                NodeRun.status == NodeRunStatus.RUNNING,
            )
        )
        return result.scalar() or 0

    async def _get_upstream_outputs(
        self, session: AsyncSession, pipeline_run_id: str, node_id: str
    ) -> dict[str, dict[str, Any]]:
        """Get outputs from upstream Done nodes for template resolution."""
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

        # Get outputs from Done nodes
        result = await session.execute(
            select(NodeRun).where(
                NodeRun.pipeline_run_id == pipeline_run_id,
                NodeRun.node_id.in_(upstream_ids),
                NodeRun.status == NodeRunStatus.DONE,
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

    @staticmethod
    def _execute_node_in_process(spec: dict[str, Any]) -> dict[str, Any]:
        """Execute a node in a separate process.

        Connections are already resolved in the main process before submission.

        Args:
            spec: Dict with node_type, node_id, node_config, pipeline_params,
                  upstream_outputs, pipeline_run_id

        Returns:
            Dict with success, outputs, logs, error keys
        """
        from app.core.template_resolver import resolve_dict_values
        from app.nodes.registry import NodeRegistry

        # Ensure registry is populated
        if not NodeRegistry.list_types():
            NodeRegistry.scan_nodes()

        node = NodeRegistry.create(spec["node_type"])

        if node.input_schema is None:
            return {
                "success": False,
                "outputs": {},
                "logs": [],
                "error": f"Node '{spec['node_type']}' does not define input_schema",
            }

        # Resolve Jinja2 templates + cast primitive types
        # Connections are already resolved in the main process
        resolved_config = resolve_dict_values(
            spec["node_config"],
            input_schema=node.input_schema,
            params=spec["pipeline_params"],
            upstream_outputs=spec["upstream_outputs"],
        )

        # Validate and execute via Pydantic
        try:
            inputs = node.input_schema(**resolved_config)
            output = node.execute(inputs, logger=None)

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
