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

## Next Steps (Session 3)

1. Create TypeScript types for connections
2. Create API client for connections
3. Create Connections page component with form and test functionality
4. Update App.tsx with routing

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

- Python 3.11 from `.venv/` directory
- Project root: `bachelor_thesis/` (current directory)
- Use async SQLAlchemy 2.0 throughout
- Pydantic v2 for all validation
- JSON logging format

## Development Rules

1. **Run Tests After Backend Implementation** — After writing backend functionality and tests, always run `pytest` to verify correctness
2. **Update AI_CONTEXT.md** — After completing each major task block, update this file with progress and changes
3. **Run Ruff Formatter** — After writing backend code, run `ruff format backend/` to ensure consistent code style
4. **Explain Before Changing on User Questions** — When the user asks a clarifying question about implementation decisions, first explain the reasoning behind the original implementation, then ask if they want it changed before making modifications
5. **Test Strategy** — Use testcontainers for integration tests that require any external connections (database, Redis, S3, etc.). Unit tests should only test pure functions without any external dependencies or mocking
6. **End of Session Protocol** — At the end of a session, make a git commit with all changes. Do not start tasks from the next session; instead, offer to complete or compact the current session
