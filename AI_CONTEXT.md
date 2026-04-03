# FlowForge AI Context

Project context for AI-assisted development sessions.

## Project Overview

**FlowForge** — Low-code оркестратор данных с типизированными артефактами.

### Key Architecture Concepts

1. **Stateless Nodes** — Each node is an independent task that reads from storage, processes, and writes back
2. **Connections** — Reusable credentials (PostgreSQL, S3, Spark, ClickHouse)
3. **Typed Artifacts** — Nodes declare typed outputs (`s3_path`, `model_artifact`, etc.)
4. **Dependency Resolution** — `{{ node_id.output_name }}` syntax for referencing outputs
5. **Pipeline Parameters** — Input variables for entire pipelines
6. **Celery Orchestration** — Each node runs as isolated Celery task

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI + Python 3.11 |
| Task Queue | Celery + Redis |
| Frontend | React 18 + TypeScript + @xyflow/react 12 |
| Database | PostgreSQL 14 + SQLAlchemy 2.0 (async) |
| Validation | Pydantic 2.x |
| Spark | PySpark 3.5 (Standalone) |
| Storage | MinIO (S3-compatible) |
| ML | CatBoost + Scikit-Learn |

## Session History

### Session 1 — Infrastructure Setup ✅ COMPLETED

**Goal:** Prepare infrastructure and basic project structure.

**Completed Files:**
- ✅ `docker-compose.yml` — All services (PostgreSQL, Redis, MinIO, Spark, Backend, Celery, Frontend)
- ✅ Directory structure with `__init__.py` files
- ✅ SQLAlchemy models:
  - `backend/app/models/base.py` — Async base class + session factory
  - `backend/app/models/connection.py` — Connection entity + Pydantic schemas
  - `backend/app/models/pipeline.py` — Pipeline definition + graph JSON
  - `backend/app/models/pipeline_run.py` — Execution tracking + RunStatus
  - `backend/app/models/node_run.py` — Node execution + logs/outputs
  - `backend/app/models/node_output_spec.py` — Output specs + template resolver
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
- ✅ `AI_CONTEXT.md` — This context file
- ✅ `backend/app/core/config.py` — Pydantic settings
- ✅ `backend/app/main.py` — FastAPI application (with table creation + OpenAPI export)
- ✅ `backend/app/workers/celery_app.py` — Celery configuration
- ✅ `backend/app/workers/tasks.py` — Celery tasks
- ✅ `backend/app/api/demo.py` — Demo API endpoints
- ✅ `backend/app/api/__init__.py` — API module exports

**Features Implemented:**
- Auto table creation on backend startup
- OpenAPI spec export to `backend/openapi.json`
- Demo endpoints: `/health`, `/api/v1/hello`, `/api/v1/status`
- Frontend demo page with API test buttons

**Models Summary:**
| Model | Description |
|-------|-------------|
| `Connection` | External data source credentials (postgres/clickhouse/s3/spark) |
| `Pipeline` | DAG definition with nodes/edges |
| `PipelineRun` | Pipeline execution tracking |
| `NodeRun` | Individual node execution with logs/outputs |
| `NodeOutputSpec` | Typed output specifications |

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

**API Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/connections` | Create new connection |
| GET | `/api/v1/connections` | List all connections |
| GET | `/api/v1/connections/{id}` | Get connection by ID |
| PUT | `/api/v1/connections/{id}` | Update connection |
| DELETE | `/api/v1/connections/{id}` | Delete connection |
| POST | `/api/v1/connections/{id}/test` | Test connection |

**Models Summary:**
| Model | Description |
|-------|-------------|
| `ConnectionType` | Enum: postgres, clickhouse, s3, spark |
| `ConnectionCreateRequest` | Request model for creating connection |
| `ConnectionUpdateRequest` | Request model for updating connection |
| `ConnectionTestResult` | Result of connection test |

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

## Next Steps (Session 4)

1. Create Pipeline and Node models/schemas (if not already done)
2. Implement Pipeline CRUD API
3. Create Pipeline list page
4. Implement Pipeline editor with @xyflow/react (node-based DAG editor)

## File Structure

```
backend/
├── app/
│   ├── api/           # FastAPI endpoints
│   ├── core/          # Config, security, logging
│   ├── models/        # SQLAlchemy models ✅ DONE
│   ├── schemas/       # Pydantic schemas (in models/*.py)
│   ├── connections/   # Connection managers
│   ├── nodes/         # Node implementations
│   ├── orchestration/ # Graph resolution, context
│   └── workers/       # Celery tasks & config
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── requirements.txt
└── pytest.ini

frontend/
├── src/
│   ├── components/
│   ├── flows/
│   ├── api/
│   └── types/
├── package.json
└── tsconfig.json
```

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://flowforge:flowforge_secret@localhost:5432/flowforge

# Redis
REDIS_URL=redis://localhost:6379/0

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=flowforge_admin
MINIO_SECRET_KEY=flowforge_secret

# Spark
SPARK_MASTER=spark://localhost:7077
```

## Notes

- Python 3.11 from `.venv/` directory in project root
- Project root: `bachelor_thesis/` (current directory)
- Use async SQLAlchemy 2.0 throughout
- Pydantic v2 for all validation
- JSON logging format

## Development Rules

**⚠️ IMPORTANT:** The AI agent MUST strictly follow all development rules below. These are mandatory requirements, not suggestions.

1. **Run Tests After Backend Implementation** — After writing backend functionality and tests, always run `pytest` to verify correctness
2. **Update AI_CONTEXT.md** — After completing each major task block, update this file with progress and changes
3. **Run Ruff Formatter** — After writing backend code, run `ruff format backend/` to ensure consistent code style
4. **Explain Before Changing on User Questions** — When the user asks a clarifying question about implementation decisions, first explain the reasoning behind the original implementation, then ask if they want it changed before making modifications
5. **Test Strategy** — Use testcontainers for integration tests that require any external connections (database, Redis, S3, etc.). Unit tests should only test pure functions without any external dependencies or mocking
6. **Verify Docker Builds** — After modifying Dockerfile or docker-compose.yaml, always attempt to build the image with `docker build` or `docker-compose build` before committing changes
7. **Clean Before Session End** — Before offering to end or continue a session, clean `__pycache__` directories: `find . -type d -name "__pycache__" -exec rm -rf {} +`
8. **End of Session Protocol** — At the end of a session, make a git commit with all changes. Do not start tasks from the next session; instead, offer to complete or compact the current session
9. **Verify Frontend Changes** — Before committing frontend changes, ask the user to verify the fix works in their browser
10. **Ask on Architectural Decisions** — When facing important architectural or implementation decisions (e.g., API design, technology choices, complex patterns), the agent MUST ask the user for preference before implementing. Do not assume — explain options and wait for confirmation.
11. **Use Project Root venv** — Always use the virtual environment from the project root directory (`.venv/` in `bachelor_thesis/`). Run commands with `.venv/bin/python` or `.venv/bin/pytest` instead of system Python.

## Session 4 — Pipeline Backend + Frontend Editor

**Goal:** Implement pipeline execution engine with node architecture and visual editor.

### Backend Tasks
1. **Node Architecture** — Base class, registry, text output node (Hello World via Celery)
2. **Pipeline Execution** — Executor, graph resolver (topological sort, cycle detection), template resolver `{{ node_id.output }}`
3. **Pipeline CRUD API** — Create, read, update, delete, run pipeline
4. **Real-time Logs** — SSE streaming for pipeline run logs
5. **Integration Tests** — Test execution, template resolution, log streaming

### Frontend Tasks
6. **Types & API Client** — Pipeline/Node types, CRUD + run + SSE log client
7. **Pipeline List Page** — List, create, delete pipelines
8. **Pipeline Editor** — @xyflow/react node editor, drag-and-drop, node configuration, save/run, real-time log viewer

### Key Requirements
- Each node runs as isolated Celery task
- Template syntax: `{{ node_id.output_name }}` for cross-node references
- Real-time log streaming (SSE or WebSocket — ask user for preference)
- Graph validation: detect cycles, validate connections
- Follow Development Rules (tests, formatting, commits)

**Start with Task 1 (Node Architecture).**
