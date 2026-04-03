# FlowForge Project Architecture

## Project Overview

**FlowForge** — Low-code оркестратор данных с типизированными артефактами.

### Key Architecture Concepts

1. **Stateless Nodes** — Each node is an independent task that reads from storage, processes, and writes back
2. **Connections** — Reusable credentials (PostgreSQL, S3, Spark, ClickHouse)
3. **Typed Artifacts** — Nodes declare typed outputs (`s3_path`, `model_artifact`, etc.)
4. **Dependency Resolution** — `{{ node_id.output_name }}` syntax for referencing outputs
5. **Pipeline Parameters** — Input variables for entire pipelines
6. **ProcessPoolExecutor Orchestration** — Nodes run in isolated processes (like Airflow LocalExecutor)

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI + Python 3.11 |
| Task Queue | ProcessPoolExecutor (local) / Celery + Redis (distributed) |
| Frontend | React 18 + TypeScript + @xyflow/react 12 |
| Database | PostgreSQL 14 + SQLAlchemy 2.0 (async) |
| Validation | Pydantic 2.x |
| Spark | PySpark 3.5 (Standalone) |
| Storage | MinIO (S3-compatible) |
| ML | CatBoost + Scikit-Learn |

## File Structure

```
backend/
├── app/
│   ├── api/              # FastAPI endpoints
│   │   ├── connections.py  # Connection CRUD API
│   │   ├── pipelines.py    # Pipeline CRUD + SSE streaming
│   │   └── dependencies.py # API dependencies
│   ├── core/             # Config, security, logging
│   ├── models/           # SQLAlchemy models
│   │   ├── base.py         # Async base class + session factory
│   │   ├── connection.py   # Connection entity + Pydantic schemas
│   │   ├── pipeline.py     # Pipeline definition + graph JSON
│   │   ├── pipeline_run.py # Execution tracking + RunStatus
│   │   ├── node_run.py     # Node execution + logs/outputs
│   │   └── node_output_spec.py # Output specs + template resolver
│   ├── connections/      # Connection managers
│   ├── nodes/            # Node implementations
│   │   ├── base.py         # BaseNode, NodeContext, NodeResult
│   │   ├── registry.py     # NodeRegistry for type discovery
│   │   └── text_output.py  # TextOutputNode (Hello World)
│   ├── orchestration/    # Graph resolution, execution
│   │   ├── executor.py       # NodeExecutor (ProcessPoolExecutor)
│   │   ├── graph_resolver.py # Topological sort, cycle detection
│   │   ├── pipeline_executor.py # Pipeline orchestration
│   │   └── logger.py         # StreamingLogger for real-time logs
│   └── workers/          # Celery tasks & config
│       ├── celery_app.py   # Celery configuration
│       ├── tasks.py        # Celery tasks
│       └── node_tasks.py   # Node execution tasks
├── tests/
│   ├── unit/
│   │   ├── test_nodes.py
│   │   ├── test_graph_resolver.py
│   │   └── test_pipeline_executor.py
│   ├── integration/
│   │   ├── test_connections.py
│   │   ├── test_node_execution.py
│   │   └── test_pipelines.py
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

## API Endpoints

### Connections
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/connections` | Create new connection |
| GET | `/api/v1/connections` | List all connections |
| GET | `/api/v1/connections/{id}` | Get connection by ID |
| PUT | `/api/v1/connections/{id}` | Update connection |
| DELETE | `/api/v1/connections/{id}` | Delete connection |
| POST | `/api/v1/connections/{id}/test` | Test connection |

### Pipelines
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/pipelines` | Create pipeline |
| GET | `/api/v1/pipelines` | List pipelines |
| GET | `/api/v1/pipelines/{id}` | Get pipeline |
| PUT | `/api/v1/pipelines/{id}` | Update pipeline |
| DELETE | `/api/v1/pipelines/{id}` | Delete pipeline |
| POST | `/api/v1/pipelines/{id}/run` | Run pipeline (sync) |
| POST | `/api/v1/pipelines/{id}/run/stream` | Run pipeline (SSE stream) |
| GET | `/api/v1/pipelines/runs/{run_id}` | Get pipeline run |

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
