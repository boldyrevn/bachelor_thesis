# FlowForge Development Progress

## Session History

### Session 1 — Infrastructure Setup ✅ COMPLETED

**Goal:** Prepare infrastructure and basic project structure.

**Completed Files:**
- ✅ `docker-compose.yml` — All services (PostgreSQL, Redis, MinIO, Spark, Backend, Celery, Frontend)
- ✅ Directory structure with `__init__.py` files
- ✅ SQLAlchemy models (base, connection, pipeline, pipeline_run, node_run, node_output_spec)
- ✅ `backend/requirements.txt` — Python dependencies
- ✅ `backend/pytest.ini` — Pytest configuration
- ✅ `backend/tests/conftest.py` — Pytest fixtures
- ✅ `backend/Dockerfile` — Backend container
- ✅ `frontend/package.json` — Node dependencies
- ✅ `frontend/tsconfig.json` — TypeScript config
- ✅ `frontend/tsconfig.node.json` — TS Node config
- ✅ `frontend/Dockerfile` — Frontend container
- ✅ `frontend/vite.config.ts` — Vite configuration
- ✅ `frontend/index.html` — HTML entry point
- ✅ `frontend/src/main.tsx` — React entry point
- ✅ `frontend/src/App.tsx` — Main React component with demo UI
- ✅ `frontend/src/api/client.ts` — API client with demo endpoints
- ✅ `frontend/src/vite-env.d.ts` — Vite type definitions
- ✅ `frontend/.env` — Frontend environment variables
- ✅ `README.md` — Setup instructions + architecture diagram
- ✅ `backend/app/core/config.py` — Pydantic settings
- ✅ `backend/app/main.py` — FastAPI application (with table creation + OpenAPI export)
- ✅ `backend/app/workers/celery_app.py` — Celery configuration
- ✅ `backend/app/workers/tasks.py` — Celery tasks
- ✅ `backend/app/api/demo.py` — Demo API endpoints

**Features Implemented:**
- Auto table creation on backend startup
- OpenAPI spec export to `backend/openapi.json`
- Demo endpoints: `/health`, `/api/v1/hello`, `/api/v1/status`
- Frontend demo page with API test buttons

---

### Session 2 — Connection CRUD API ✅ COMPLETED

**Goal:** Implement Connection CRUD API with testing functionality.

**Completed Files:**
- ✅ `backend/app/schemas/connection.py` — Type-specific Pydantic schemas for config/secrets validation
- ✅ `backend/app/connections/service.py` — Connection testing service with type-specific testers
- ✅ `backend/app/api/connections.py` — CRUD API endpoints + test endpoint
- ✅ `backend/app/api/dependencies.py` — API dependencies (db session)
- ✅ `backend/tests/integration/test_connections.py` — Integration tests with testcontainers
- ✅ `backend/tests/conftest.py` — Updated fixtures for testcontainers PostgreSQL

**Features Implemented:**
- Connection CRUD endpoints (POST, GET, PUT, DELETE)
- Connection type validation (postgres, clickhouse, s3, spark)
- Base64 encoding for secrets (MVP encryption)
- Connection testing endpoint with type-specific testers
- Integration tests using testcontainers PostgreSQL (14 tests passing)

---

### Session 3 — Frontend Connections Page ✅ COMPLETED

**Goal:** Create frontend Connections page with CRUD operations.

**Completed Files:**
- ✅ `frontend/src/types/connection.ts` — TypeScript types for connections
- ✅ `frontend/src/api/connections.ts` — API client for connections endpoints
- ✅ `frontend/src/components/ConnectionsPage.tsx` — Connections page with list, add/edit modal, test, delete
- ✅ `frontend/src/App.tsx` — Updated with React Router and AppShell navigation
- ✅ `frontend/src/main.tsx` — Added QueryClientProvider and Notifications

**Features Implemented:**
- Connection list table with type badges
- Add/Edit modal with dynamic form fields per connection type
- Test button with toast notifications (individual loading state per connection)
- Delete functionality with confirmation
- React Router navigation with Mantine AppShell layout
- Dynamic form fields:
  - PostgreSQL: host, port, database, username, password
  - ClickHouse: host, port, database, username, password
  - S3: endpoint, region, default_bucket, use_ssl (switch), access_key, secret_key
  - Spark: master_url, app_name, deploy_mode, spark_home

**Fixes Applied:**
- Added `QueryClientProvider` wrapper (fixed white screen error)
- Added `use_ssl` field to `S3Config` schema and frontend type
- Fixed test button loading state to show only for clicked connection

**Dependencies Added:**
- `@mantine/notifications` — Toast notifications

---

### Session 4 — Pipeline Backend (Tasks 1-5) ✅ COMPLETED

**Goal:** Implement pipeline execution engine with node architecture, CRUD API, and SSE streaming.

**Completed Files:**
- ✅ `backend/app/nodes/base.py` — BaseNode, NodeContext, NodeResult
- ✅ `backend/app/nodes/registry.py` — NodeRegistry for type discovery
- ✅ `backend/app/nodes/text_output.py` — TextOutputNode with template resolution
- ✅ `backend/app/orchestration/executor.py` — NodeExecutor (ProcessPoolExecutor) with log streaming
- ✅ `backend/app/orchestration/graph_resolver.py` — Topological sort, cycle detection
- ✅ `backend/app/orchestration/pipeline_executor.py` — Pipeline orchestration with template resolution
- ✅ `backend/app/orchestration/logger.py` — StreamingLogger for real-time logs
- ✅ `backend/app/workers/node_tasks.py` — Celery task wrapper for node execution
- ✅ `backend/app/api/pipelines.py` — Pipeline CRUD API + SSE streaming endpoint
- ✅ `backend/tests/unit/test_nodes.py` — 26 unit tests
- ✅ `backend/tests/unit/test_graph_resolver.py` — 18 unit tests
- ✅ `backend/tests/unit/test_pipeline_executor.py` — 18 unit tests
- ✅ `backend/tests/integration/test_node_execution.py` — 19 integration tests
- ✅ `backend/tests/integration/test_pipelines.py` — 18 integration tests

**Features Implemented:**
- Node Architecture: BaseNode, NodeRegistry, TextOutputNode
- Node Executor: ProcessPoolExecutor-based execution (like Airflow LocalExecutor)
- Real-time log streaming via multiprocessing.Queue and async generators
- Graph Resolver: Topological sort (Kahn's algorithm), cycle detection (DFS)
- Pipeline Executor: Orchestrates node execution in topological order
- Template resolution: `{{ node_id.output }}` and `{{ params.name }}` syntax
- Pipeline CRUD API: Create, Read, Update, Delete, Run, Run with SSE stream
- SSE endpoint for real-time log streaming during pipeline execution

**Test Results:** 115 tests passing (62 unit + 53 integration)

**SSE Stream Format:**
```json
// Log event
{"type": "log", "node_id": "node-1", "level": "INFO", "message": "Starting...", "timestamp": "..."}

// Result event
{"type": "result", "success": true, "node_results": {...}}

// Error event
{"type": "error", "error": "..."}
```

---

### Session 5 — Pipeline Editor Frontend ✅ COMPLETED

**Goal:** Implement Pipeline Editor with @xyflow/react, custom nodes, directed edges, and collapsible navbar.

**Completed Files:**
- ✅ `frontend/src/flows/PipelineEditor.tsx` — Main editor with 3-column resizable layout (params | canvas | node list)
- ✅ `frontend/src/flows/nodes/FlowNode.tsx` — Custom node with source (bottom) and target (top) handles only
- ✅ `frontend/src/flows/edges/FlowEdge.tsx` — Custom directed edge with arrow markers
- ✅ `frontend/src/flows/ConnectionDragContext.tsx` — Context for tracking active connection drag state
- ✅ `frontend/src/flows/ResizeHandle.tsx` — Draggable resize handle for panel width adjustment
- ✅ `frontend/src/types/pipeline.ts` — TypeScript types (PipelineNode, GraphDefinition, SSEEvent, RunStatus)
- ✅ `frontend/src/components/PipelinesPage.tsx` — Placeholder page with "New Pipeline" button
- ✅ `frontend/src/App.tsx` — Collapsible navbar, breadcrumbs, routing for /pipelines and /pipelines/new

**Features Implemented:**
- **Custom FlowNode**: Source handle (bottom, output only) and target handle (top, input only)
- **Directed Edges**: Arrow markers that are light gray by default, dark gray when selected
- **Green Target Highlight**: Target handles turn green during connection drag (except source node)
- **ConnectionDragContext**: Tracks which node is being dragged from for real-time UI feedback
- **3-Column Resizable Layout**: Pipeline params | Canvas | Node list/params with draggable borders
- **"Add Node" Dropdown**: Button on canvas to add nodes (Text Output, Pipeline Params)
- **Node Selection**: Click to select, view params in right panel, delete from list
- **Collapsible Navbar**: Hidden by default, toggled via burger menu in header
- **Breadcrumbs**: Navigation trail in header (Home > Pipelines > New Pipeline)
- **PageWrapper**: Consistent padding for non-editor routes, zero padding for editor

**UI/UX Details:**
- Navbar: Collapsed=60px (icons only), Expanded=250px (icons + labels)
- Icon positioning: Fixed 20px left offset for stable alignment
- Active nav item: Blue highlight with rounded corners
- Arrow button: Centered in 60px container with full-width top border

**Verified:**
- Docker build successful
- Manual browser testing at http://localhost:3000/pipelines/new

---

### Session 6 — Typed Node Parameters, Jinja2 Templates & Auto-Discovery ✅ COMPLETED

**Goal:** Redesign node architecture to use typed input/output schemas with automatic metadata discovery, database persistence, and full Jinja2 template resolution.

**Completed Files:**
- ✅ `backend/app/nodes/base.py` — Rewritten with Generic[InputT, OutputT], typed schemas, Pydantic validation
- ✅ `backend/app/nodes/registry.py` — Added scan_nodes() for module discovery
- ✅ `backend/app/nodes/scanner.py` — NEW: NodeScanner service for DB persistence
- ✅ `backend/app/nodes/text_output.py` — Refactored to use typed Input/Output schemas
- ✅ `backend/app/core/template_resolver.py` — NEW: Jinja2 template resolver utility
- ✅ `backend/app/models/node_type.py` — NEW: NodeType SQLAlchemy model for node metadata
- ✅ `backend/app/api/node_types.py` — NEW: API endpoints for listing/scanning node types
- ✅ `backend/app/orchestration/executor.py` — Updated to work with typed parameters + Jinja2 resolution
- ✅ `backend/app/main.py` — Added startup node scanning hook, fixed logger initialization
- ✅ `backend/tests/unit/test_nodes.py` — Rewritten for new typed architecture (36 tests)
- ✅ `backend/tests/integration/test_node_types.py` — NEW: Integration tests for scanner & API (8 tests)
- ✅ `backend/tests/integration/test_node_execution.py` — Updated for typed schemas + Jinja2
- ✅ `backend/tests/integration/test_pipelines.py` — Fixed test isolation issue
- ✅ `docker-compose.yaml` — Removed Redis and Celery services, cleaned backend deps

**Architecture Changes:**
- **Typed Node Parameters**: Nodes declare `input_schema` and `output_schema` as Pydantic BaseModel classes
- **Simplified execute()**: `execute(inputs: InputT, logger: logging.Logger) -> OutputT`
  - No NodeContext - Scheduler will handle context assembly later
  - No validation in nodes - Executor validates inputs before calling execute()
  - Node only executes code with validated inputs and logs via logger
- **Jinja2 Template Resolution**: Full Jinja2 templating for node inputs
  - `{{ params.name }}` - Pipeline parameters
  - `{{ node_id.output_name }}` - Upstream node outputs
  - `{{ params.date | upper }}` - Jinja2 filters
  - `{% if params.env == 'prod' %}...{% endif %}` - Control structures
  - Note: Use underscores in node IDs (`node_a` not `node-a`) for Jinja2 compatibility
- **Node Scanner**: Auto-discovers nodes from `app.nodes` package and persists metadata to DB
- **NodeType DB Model**: Stores title, description, category, input/output JSON schemas
- **HTTP API for Frontend**:
  - `GET /api/v1/node-types` — List all node types with titles, descriptions, categories, input/output JSON schemas
  - `GET /api/v1/node-types/{id}` — Get specific node type metadata
  - `POST /api/v1/node-types/scan` — Rescan and sync node metadata to DB
- **Startup Hook**: Automatically scans and persists node types on app startup
- **Frontend Benefits**: No hardcoded node types - forms generated from JSON schemas
- **Infrastructure Cleanup**: Removed Redis and Celery from docker-compose

**Node Type Schema Example:**
```python
class TextOutputInput(BaseModel):
    message: str = Field(default="Hello, World!", description="Text message to output")

class TextOutputOutput(BaseModel):
    text: str = Field(description="The output message")

@NodeRegistry.register
class TextOutputNode(BaseNode[TextOutputInput, TextOutputOutput]):
    node_type = "text_output"
    title = "Text Output"
    description = "Outputs a text message"
    category = "output"
    input_schema = TextOutputInput
    output_schema = TextOutputOutput

    def execute(self, inputs: TextOutputInput, logger: logging.Logger) -> TextOutputOutput:
        logger.info(f"Processing: {inputs.message}")
        return TextOutputOutput(text=inputs.message)
```

**Test Results:** 119 tests passing

**Breaking Changes:**
- Node `execute()` signature simplified: `execute(inputs, logger)` (no context)
- Node validation moved to executor - validates before execute()
- Logs are streamed separately, not returned in result dict
- **Jinja2 templates**: Use `node_a` instead of `node-a` in node IDs (hyphens are subtraction in Jinja2)

**Dependencies Added:**
- `jinja2==3.1.3` - Full Jinja2 template resolution

**Fixes Applied:**
- `NameError: name 'logger' is not defined` on startup — added `logger = logging.getLogger(__name__)`

**Services Remaining in docker-compose:**
- PostgreSQL (metadata DB)
- MinIO (S3 storage + init)
- Spark Master/Worker
- Backend (FastAPI)
- Frontend (React)

---

### Session 7 — Typed Connection Classes, MultilineStr, Node Input Validation & Dynamic Node Discovery ✅ COMPLETED

**Goal:** Redesign connection types as typed Pydantic classes with `test()` method, add custom `MultilineStr` type, validate node input schemas, implement hot-reload node discovery (Airflow-style `exec()`-based scanning), and integrate connection fields in AddNodeDialog.

**Completed Files:**
- ✅ `backend/app/schemas/connection.py` — Rewritten with `BaseConnection`, `Secret`, typed classes (`PostgresConnection`, `ClickHouseConnection`, `S3Connection`, `SparkConnection`), each with `test()` method and `x-connection-type` JSON schema marker
- ✅ `backend/app/schemas/node_types.py` — `MultilineStr` custom type (Annotated with `format: multiline`)
- ✅ `backend/app/schemas/node_input_validation.py` — Validates node input schemas: only allows primitives, MultilineStr, connection subclasses, nested BaseModel
- ✅ `backend/app/connections/service.py` — Simplified to use typed connection classes' `test()` method
- ✅ `backend/app/api/connections.py` — Updated CRUD API, added `GET /api/v1/connections/types` endpoint for frontend form generation
- ✅ `backend/app/nodes/registry.py` — Rewritten `scan_nodes()` with Airflow-style `exec()`-based file scanning (no import sys conflicts, supports hot-reload of add/delete/change node files)
- ✅ `backend/app/nodes/scanner.py` — Calls `scan_nodes()` before listing types for dynamic discovery
- ✅ `backend/app/nodes/postgres_query.py` — New node: connects to PostgreSQL via `PostgresConnection` field, lists schemas/tables
- ✅ `backend/app/nodes/add_two_numbers.py` → `multiply_two_numbers.py` — Tested hot-reload of node swap
- ✅ `frontend/src/flows/AddNodeDialog.tsx` — Added reload button (triggers server scan), resolves connection types from `$ref` + `$defs` in JSON schema, shows multiline string labels
- ✅ `frontend/src/flows/PipelineEditor.tsx` — Fixed long node name rendering (k-icon doesn't shrink, close button stays right)
- ✅ `frontend/src/api/connections.ts` — Restored `connectionsApi` for ConnectionsPage compatibility, added `getConnectionTypes()`
- ✅ `frontend/src/types/connection.ts` — Added `Connection` and `ConnectionTypeSchema` interfaces
- ✅ `backend/tests/unit/test_connection_types.py` — 30 unit tests for Secret, Connection classes, MultilineStr, input validation
- ✅ `backend/tests/integration/test_connections.py` — Updated for new connection architecture (19 integration tests)

**Architecture Changes:**
- **Connection Classes** — Each connection type is a single Pydantic class with `test()`, `SECRET_FIELDS`, and `x-connection-type` marker in JSON schema
- **Secret Wrapper** — Single `Secret` class replaces per-connection Secrets models; auto-wraps strings, stores as base64
- **Airflow-style Node Discovery** — `scan_nodes()` uses `exec()` on .py files with a prepared namespace (no import conflicts, no `__init__.py` imports needed, full hot-reload support)
- **Input Schema Validation** — Scanner validates node input types before persisting to DB
- **Hot-reload** — New/changed/deleted node files are detected on reload without container restart

**Test Results:** 151 tests passing (30 unit + 19 integration + 102 existing)

---

### Session 8 — Pipeline Save/Load, List Page & Node Param Validation ✅ COMPLETED

**Goal:** Implement pipeline save/load, pipeline list page with CRUD, and backend validation of node parameters.

**Completed Files:**
- ✅ `frontend/src/api/pipelines.ts` — NEW: API client for pipeline CRUD + run endpoints
- ✅ `frontend/src/components/PipelineListPage.tsx` — NEW: Pipeline list table with create/edit/run/delete
- ✅ `frontend/src/context/HeaderActionsContext.tsx` — NEW: Context for registering page-level header actions
- ✅ `frontend/src/flows/PipelineEditor.tsx` — Rewritten: Save button in header, Name field in left panel, redirect on save, node selection sync
- ✅ `frontend/src/App.tsx` — HeaderActionsProvider, HeaderActionsSlot, routing updates
- ✅ `frontend/src/types/nodeType.ts` — Added index signature for React Flow compatibility
- ✅ `backend/app/orchestration/graph_resolver.py` — Added `validate_node_params()` to validate node configs against Pydantic schemas
- ✅ `backend/tests/unit/test_pipeline_executor.py` — Fixed node ID conventions (underscores)
- ✅ `backend/tests/integration/test_pipelines.py` — Fixed node ID conventions

**Features Implemented:**
- **Save Button in Header**: Registered via HeaderActionsContext, appears next to breadcrumbs
- **Name Field in Left Panel**: No modal dialog — pipeline name is always visible and editable
- **Auto-redirect on Save**: After successful save, navigate to `/pipelines` list page
- **Pipeline List Page**: Table with name, graph stats (nodes/edges), created date, actions (edit/run/delete)
- **Create Pipeline Modal**: On list page with name + description fields
- **Node Selection Sync**: Click node on canvas → right panel shows params; click node in list → canvas centers + highlights; click X → deselect
- **Stale Closure Fix**: `graphRef` and `formValuesRef` for latest state in save button closure
- **Node Parameter Validation**: Backend validates node configs against input_schema Pydantic models in `validate_pipeline_graph()`
- **Error Handling**: Pydantic validation errors shown as user-friendly toast notifications; duplicate name conflict modal

**API Changes:**
- `GET /api/v1/pipelines` — List all pipelines
- `GET /api/v1/pipelines/{id}` — Get single pipeline
- `POST /api/v1/pipelines` — Create pipeline (with graph validation)
- `PUT /api/v1/pipelines/{id}` — Update pipeline (with graph validation)
- `DELETE /api/v1/pipelines/{id}` — Delete pipeline

**Test Results:** 153 tests passing (all unit + integration)

**Verified:**
- Full save cycle: create pipeline → add node → save → appears in list → edit → save again
- Validation: empty required params rejected with error toast
- Duplicate name: conflict modal shown
- Type check: `npx tsc --noEmit` clean for all frontend files

---

## Next Steps

### Frontend Tasks (remaining)
- ~~Pipeline List Page~~ ✅ COMPLETED (Session 8)
- ~~Save/Load Pipeline~~ ✅ COMPLETED (Session 8)
- Pipeline Run + SSE Log Viewer
- Pipeline Parameters (left panel) — dynamic key-value editor

---

### Session 9 — Bug Fixes, Runs Page & Connection UUID Resolution ✅ COMPLETED

**Goal:** Fix bugs from previous sessions, add Pipeline Runs page, fix connection UUID resolution in node configs.

**Completed Files:**
- ✅ `frontend/src/context/PipelineNameContext.tsx` — NEW: Context for sharing pipeline name between editor and breadcrumbs
- ✅ `frontend/src/components/NodeParamsForm.tsx` — Fixed: no Divider after last parameter; added `i` icon with tooltip for output params description
- ✅ `frontend/src/flows/PipelineEditor.tsx` — Fixed: Save stays on update page (no redirect); fixed `getNodeType` fetch on every character (extracted `selectedNodeType` state)
- ✅ `frontend/src/App.tsx` — Fixed breadcrumbs using `pathname` regex extraction instead of `useParams()` (which doesn't work outside `<Routes>`); added `PipelineNameProvider`
- ✅ `frontend/src/components/PipelineRunsPage.tsx` — NEW: Full run list page with table (Run ID, Pipeline, Status, Started, Duration, Error)
- ✅ `frontend/src/api/pipelines.ts` — Added `getAllRuns()` for fetching all runs across pipelines
- ✅ `backend/app/api/pipeline_runs.py` — Added `GET /api/v1/pipelines/runs` for listing all runs
- ✅ `backend/app/main.py` — Registered `global_runs_router` before parameterized routes
- ✅ `backend/app/orchestration/graph_resolver.py` — Rewrote `validate_node_params()`: only checks required fields present and connection UUID validity (full type validation deferred to runtime for Jinja2 compatibility)
- ✅ `backend/app/orchestration/executor.py` — Rewrote `_resolve_connections()`: proper async DB lookup with `asyncio.run()`, resolves UUID strings to typed `BaseConnection` objects via `assemble_connection()`
- ✅ `frontend/src/components/NodeParamsForm.tsx` — Added output params `i` icon with tooltip description

**Bug Fixes:**
- **Breadcrumbs "Loading..." forever**: `useParams()` returns `undefined` outside `<Routes>` → switched to `pathname` regex extraction
- **Save redirects to list page**: Changed to stay on update page after save; new pipelines redirect to their update page
- **`getNodeType` fetch on every character**: `useEffect` depended on `nodes` array → extracted `selectedNodeType` string state
- **Postgres Query connection UUID rejected**: Validation now uses `TypeAdapter` for field-by-field checks; connection fields resolved at runtime in executor
- **Jinja2 templates blocked type validation**: `validate_node_params()` now only checks required fields present + connection UUID validity; full type validation deferred to runtime after template resolution
- **Divider after last parameter**: Added `isLast` check to skip Divider

**Architecture Decisions:**
- **Connection UUID resolution**: Frontend sends connection UUID string; backend resolves to typed `BaseConnection` in executor via DB lookup + `assemble_connection()`
- **Deferred type validation**: Since node configs may contain Jinja2 templates (`{{ upstream.result }}`), full type validation is done at runtime after template resolution; save-time validation only checks required fields present + connection UUID format

**Test Results:** 161 tests passing

**Verified via MCP:**
- Save with connection UUID → 200 ✅
- Save with Jinja2 template → 200 ✅
- Save without required connection → 400 "connection is required" ✅
- Run pipeline with postgres_query + connection → 201 success ✅
- Runs page displays all pipeline runs ✅
