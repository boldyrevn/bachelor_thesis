# FlowForge

**Low-code оркестратор данных с типизированными артефактами**

FlowForge — это платформа для визуального проектирования и выполнения ETL/ML пайплайнов. Главная особенность — типизированные артефакты и декларативное разрешение зависимостей между нодами.

## Архитектура

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FlowForge Architecture                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │   Frontend   │────▶│   Backend    │────▶│   Celery     │                │
│  │  React Flow  │     │   FastAPI    │     │   Workers    │                │
│  └──────────────┘     └──────────────┘     └──────────────┘                │
│         │                   │                   │                           │
│         │                   │                   │                           │
│         ▼                   ▼                   ▼                           │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │   Browser    │     │  PostgreSQL  │     │    Redis     │                │
│  │              │     │   (metadata) │     │   (broker)   │                │
│  └──────────────┘     └──────────────┘     └──────────────┘                │
│                            │                   │                           │
│                            ▼                   ▼                           │
│                     ┌──────────────┐     ┌──────────────┐                  │
│                     │    MinIO     │     │    Spark     │                  │
│                     │  (artifacts) │     │  (compute)   │                  │
│                     └──────────────┘     └──────────────┘                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Ключевые Концепции

### 1. Stateless Nodes
Каждая нода — независимая задача, которая читает из хранилища, обрабатывает и пишет результат.

### 2. Коннекторы
Централизованное хранение учетных данных (секреты кодируются в base64):
- **PostgreSQL** — хост, порт, база данных, пользователь, пароль
- **ClickHouse** — хост, порт, база данных, пользователь, пароль
- **S3** — endpoint, access key, secret key, регион, бакет
- **Spark** — master URL, app name, deploy mode

### 3. Типизированные Артефакты
Ноды декларируют выходы с типами:
- `s3_path` — путь к файлу в S3
- `db_table` — имя таблицы в БД
- `model_artifact` — сериализованная ML модель
- `string` / `number` — скалярные значения

### 4. Разрешение Зависимостей
Синтаксис `{{ node_id.output_name }}` для ссылок на артефакты:
```yaml
node_2:
  input_path: "{{ node_1.s3_path }}"
```

## Технологический Стек

| Компонент | Технология |
|-----------|------------|
| Backend | FastAPI + Python 3.11 |
| Task Queue | Celery + Redis |
| Frontend | React 18 + TypeScript + @xyflow/react 12 |
| Database | PostgreSQL 14 + SQLAlchemy 2.0 (async) |
| Validation | Pydantic 2.x |
| Spark | PySpark 3.5 (Standalone) |
| Storage | MinIO (S3-compatible) |
| ML | CatBoost + Scikit-Learn |
| Tests | pytest + testcontainers |

## Быстрый Старт

### Требования

- Docker + Docker Compose
- Python 3.11 (для локальной разработки)
- Node.js 18+ (для локальной разработки фронтенда)

### Запуск через Docker Compose

```bash
# Запуск всех сервисов
docker-compose up -d

# Проверка статуса
docker-compose ps

# Просмотр логов
docker-compose logs -f backend

# Остановка
docker-compose down
```

### Сервисы

| Сервис | Порт | Описание |
|--------|------|----------|
| Frontend | 3000 | React приложение |
| Backend | 8000 | FastAPI API |
| PostgreSQL | 5432 | Метаданные |
| Redis | 6379 | Celery брокер |
| MinIO | 9000/9001 | S3 хранилище |
| Spark Master | 7077/8080 | Spark кластер |

### Доступ к интерфейсам

- **Frontend:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs
- **MinIO Console:** http://localhost:9001 (flowforge_admin / flowforge_secret)
- **Spark UI:** http://localhost:8080

## Структура Проекта

```
.
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI endpoints
│   │   │   ├── connections.py    # Connection CRUD API
│   │   │   ├── demo.py           # Demo endpoints
│   │   │   └── dependencies.py   # API dependencies
│   │   ├── core/          # Config, security, logging
│   │   ├── models/        # SQLAlchemy models
│   │   ├── schemas/       # Pydantic schemas
│   │   │   └── connection.py     # Connection type schemas
│   │   ├── connections/   # Connection managers
│   │   │   └── service.py        # Connection testing service
│   │   ├── nodes/         # Node implementations
│   │   ├── orchestration/ # Graph resolution, context
│   │   └── workers/       # Celery tasks
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   │   └── test_connections.py  # Connection API tests
│   │   └── conftest.py
│   ├── requirements.txt
│   └── pytest.ini
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── flows/
│   │   ├── api/
│   │   └── types/
│   ├── package.json
│   └── tsconfig.json
├── docker/
│   ├── spark/
│   └── minio/
├── docker-compose.yml
├── AI_CONTEXT.md
└── README.md
```

## Локальная Разработка

### Backend

```bash
cd backend

# Создание виртуального окружения
python3.11 -m venv .venv
source .venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Запуск сервера
uvicorn app.main:app --reload --port 8000

# Запуск тестов
pytest

# Запуск Celery worker
celery -A app.workers.celery_app worker --loglevel=info
```

### Frontend

```bash
cd frontend

# Установка зависимостей
npm install

# Запуск dev сервера
npm run dev
```

## Переменные Окружения

Создайте `.env` файл в корне проекта:

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

## Тестирование

```bash
cd backend

# Все тесты
pytest

# Только unit тесты
pytest -m unit

# Только integration тесты (требует Docker)
pytest -m integration

# С покрытием
pytest --cov=app --cov-report=html
```

## API Endpoints

### Connections API

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/v1/connections` | Создать новый коннектор |
| GET | `/api/v1/connections` | Получить список всех коннекторов |
| GET | `/api/v1/connections/{id}` | Получить коннектор по ID |
| PUT | `/api/v1/connections/{id}` | Обновить коннектор |
| DELETE | `/api/v1/connections/{id}` | Удалить коннектор |
| POST | `/api/v1/connections/{id}/test` | Протестировать соединение |

#### Пример создания PostgreSQL коннектора

```bash
curl -X POST http://localhost:8000/api/v1/connections \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-postgres",
    "connection_type": "postgres",
    "config": {
      "host": "localhost",
      "port": 5432,
      "database": "mydb",
      "username": "user"
    },
    "secrets": {
      "password": "mypassword"
    },
    "description": "Production PostgreSQL"
  }'
```

#### Пример тестирования соединения

```bash
curl -X POST http://localhost:8000/api/v1/connections/{id}/test
```

Ответ:
```json
{
  "success": true,
  "message": "Successfully connected to PostgreSQL at localhost:5432"
}
```

## Roadmap

### Session 1 — Infrastructure ✅
- Docker Compose со всеми сервисами
- Структура проекта
- SQLAlchemy модели
- Базовая конфигурация

### Session 2 — Connection CRUD API ✅
- Pydantic схемы для валидации конфигов/секретов
- CRUD API для коннекторов (POST, GET, PUT, DELETE)
- Сервис тестирования соединений
- Интеграционные тесты с testcontainers (14 тестов)

### Session 3 — Pipeline Editor (В разработке)
- React Flow интеграция
- Визуальный редактор нод
- Валидация графа

### Session 4 — Node Implementations
- PipelineParams нода
- PostgresToS3 нода
- TrainTestSplit нода
- CatBoostTrain нода

### Session 5 — Orchestration
- Разрешение зависимостей
- Celery задачи
- Логирование и статусы

### Session 6 — Polish
- UI улучшения
- Документация
- Финальное тестирование

## Вклад в Проект

### Правила Разработки

1. **Тесты после реализации** — После написания функционала всегда запускайте `pytest`
2. **Форматирование** — Используйте `ruff format backend/` для форматирования кода
3. **Интеграционные тесты** — Используйте testcontainers для тестов с внешними зависимостями
4. **Юнит-тесты** — Тестируйте только чистые функции без внешних зависимостей

## Лицензия

MIT License — см. [LICENSE](LICENSE)
