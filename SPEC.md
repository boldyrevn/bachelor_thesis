# Technical Specification: Low-Code ETL & ML Orchestrator

## 1. Project Overview
**Name:** FlowETL (Working Title)  
**Type:** Bachelor Thesis Project  
**Goal:** Develop a low-code platform for designing, executing, and monitoring data pipelines (ETL/ELT) with integrated Machine Learning capabilities.  
**Key Concept:** Unified interface for heterogeneous data sources (Relational DBs, Object Storage). Object Storage (S3) is treated as a first-class data source, not just temporary storage.  
**Deployment:** Local-first via Docker Compose, scalable architecture.

## 2. Architecture Principles
1.  **Decoupled Compute & Storage:** Execution logic (Workers) is separated from data storage (PostgreSQL, MinIO, External DBs).
2.  **Type-Safe Data Contracts:** Pipeline blocks define strict input/output types (e.g., `DB_TABLE`, `S3_FILE`, `ML_MODEL`). UI prevents invalid connections.
3.  **Hybrid Execution:** 
    *   SQL transformations can execute inplace (Push-down) within the source DB.
    *   Python/ML transformations execute in isolated Workers using data from Object Storage.
4.  **Security:** All connection credentials (passwords, keys) are encrypted at rest in the metadata database.

## 3. Technology Stack
| Component | Technology | Version | Notes |
| :--- | :--- | :--- | :--- |
| **Backend API** | Python, FastAPI | 3.10+, 0.100+ | Async support, Pydantic V2 |
| **ORM** | SQLAlchemy | 2.0+ | AsyncIO engine |
| **Task Queue** | Celery | 5.3+ | Redis as Broker & Backend |
| **Broker/Cache** | Redis | 7+ | For Celery & App Caching |
| **Metadata DB** | PostgreSQL | 15+ | Stores configs, logs, users |
| **Object Storage** | MinIO | Latest | S3-Compatible API (Data Lake) |
| **Frontend** | React, TypeScript | 18+, 5+ | Vite build tool |
| **Graph Editor** | React Flow | 11+ | Node-based UI |
| **UI Framework** | TailwindCSS, Shadcn/UI | - | Rapid UI development |
| **ML Libraries** | CatBoost, Pandas | Latest | Installed in Worker Image |
| **Infrastructure** | Docker, Docker Compose | - | Single command deployment |

## 4. Core Entities & Data Model

### 4.1. Connections (`connections` table)
Represents external systems accessible by the platform.
- `id`: UUID (PK)
- `name`: String (Unique)
- `type`: Enum (`POSTGRES`, `CLICKHOUSE`, `S3`, `SPARK`)
- `config`: JSONB (Encrypted) 
  - Example PG: `{"host": "...", "port": 5432, "user": "...", "password": "...", "db": "..."}`
  - Example S3: `{"endpoint": "...", "bucket": "...", "access_key": "...", "secret_key": "..."}`
- `created_at`: DateTime

### 4.2. Pipelines (`pipelines` table)
Definition of the DAG (Directed Acyclic Graph).
- `id`: UUID (PK)
- `name`: String
- `graph_definition`: JSONB (Stores nodes, edges, positions from React Flow)
- `is_active`: Boolean
- `updated_at`: DateTime

### 4.3. Executions (`executions` table)
Runtime instances of pipelines.
- `id`: UUID (PK)
- `pipeline_id`: UUID (FK)
- `status`: Enum (`PENDING`, `RUNNING`, `SUCCESS`, `FAILED`)
- `started_at`: DateTime
- `finished_at`: DateTime

### 4.4. Tasks (`tasks` table)
Runtime instances of individual blocks within an execution.
- `id`: UUID (PK)
- `execution_id`: UUID (FK)
- `block_id`: String (Reference to graph node ID)
- `status`: Enum (`PENDING`, `RUNNING`, `SUCCESS`, `FAILED`)
- `logs`: Text (Stored output/stderr)
- `output_metadata`: JSONB (e.g., `{"type": "S3_FILE", "path": "s3://..."}`)

## 5. Block System & Data Contracts

Blocks are the atomic units of processing. Each block has defined **Input Ports** and **Output Ports** with strict types.

### 5.1. Data Types (Contracts)
1.  `DB_TABLE`: Reference to a table/query result within a specific DB Connection.
2.  `S3_FILE`: Reference to a file path in Object Storage (e.g., `s3://bucket/path/file.parquet`).
3.  `ML_MODEL`: Reference to a serialized model artifact in Object Storage.
4.  `TRIGGER`: No data, used for scheduling/manual start.

### 5.2. Standard Block Types
| Block Name | Input Type | Output Type | Description |
| :--- | :--- | :--- | :--- |
| `DB Extract` | `TRIGGER` | `S3_FILE` | Connects to DB, runs SQL, exports result to Parquet in S3. |
| `S3 Transform` | `S3_FILE` | `S3_FILE` | Runs Python/Pandas script on file in S3, saves new file. |
| `DB Transform` | `DB_TABLE` | `DB_TABLE` | Executes SQL (CREATE TABLE AS) inplace within the DB. |
| `CatBoost Train` | `S3_FILE` | `ML_MODEL` | Trains model on dataset from S3, saves artifact to S3. |
| `DB Load` | `S3_FILE` | `DB_TABLE` | Loads data from S3 file into DB table. |
| `S3 Source` | `TRIGGER` | `S3_FILE` | References an existing file in S3. |

### 5.3. Execution Logic
1.  **Orchestrator** parses the graph, performs topological sort.
2.  **Celery Tasks** are dispatched based on dependencies.
3.  **Workers** execute the logic. 
    *   If Block requires S3: Worker uses `boto3` to read/write from MinIO.
    *   If Block requires DB: Worker uses `sqlalchemy` to connect to external DB.
4.  **Metadata Passing:** The output of one block (e.g., S3 path) is passed as input configuration to the dependent block via the Orchestrator.

## 6. API Structure (FastAPI)

### Auth
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/register`

### Connections
- `GET /api/v1/connections`
- `POST /api/v1/connections` (Encrypts config before save)
- `DELETE /api/v1/connections/{id}`
- `POST /api/v1/connections/{id}/test` (Validate connectivity)

### Pipelines
- `GET /api/v1/pipelines`
- `POST /api/v1/pipelines`
- `PUT /api/v1/pipelines/{id}`
- `POST /api/v1/pipelines/{id}/run` (Triggers execution)

### Executions
- `GET /api/v1/executions/{id}` (Get status)
- `GET /api/v1/executions/{id}/logs` (Stream logs)

## 7. Frontend Requirements (React)

1.  **Graph Editor:** 
    - Use `React Flow`.
    - Custom Nodes for each Block Type (display icon, status, config button).
    - **Validation:** Prevent connecting incompatible ports (e.g., `DB_TABLE` output cannot connect to `CatBoost` input).
2.  **Configuration Drawer:** 
    - When a node is selected, show a side panel with form fields based on block type (e.g., SQL Editor for DB Extract, Python Editor for Transform).
3.  **Dashboard:** 
    - List of pipelines with last run status.
    - Execution history view with logs per task.

## 8. Security & Secrets Management
- **Encryption:** Use `cryptography.fernet` for encrypting `config` JSON in `connections` table.
- **Key Management:** Encryption key stored in Environment Variable `ENCRYPTION_KEY` (not in code).
- **Network:** Services communicate via Docker internal network. MinIO and Postgres are not exposed to public host ports unless necessary for debugging.

## 9. Directory Structure

```text
/project-root
  /backend
    /app
      /api            # FastAPI routers
      /core           # Config, Security, Encryption
      /db             # SQLAlchemy models, session
      /workers        # Celery tasks, Block logic implementations
      /services       # S3 Client, DB Connectors
    Dockerfile
    requirements.txt
  /frontend
    /src
      /components     # React Flow nodes, UI components
      /hooks          # Custom hooks
      /api            # Axios instances
    Dockerfile
  /docker
    worker.Dockerfile # Includes ML libs (catboost, pandas)
  docker-compose.yml
  SPEC.md             # This file
  README.md