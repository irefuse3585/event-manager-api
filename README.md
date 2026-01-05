# Event Manager API

[![CI](https://github.com/irefuse3585/event-manager-api/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/irefuse3585/event-manager-api/actions)
![Docker](https://img.shields.io/badge/docker-ready-blue?logo=docker)
![Python](https://img.shields.io/badge/python-3.10+-blue?logo=python)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Coverage](https://img.shields.io/badge/e2e%20tested-yes-brightgreen)
![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-ff69b4?logo=pre-commit)
[![OpenAPI](https://img.shields.io/badge/docs-Swagger-blue.svg)](http://localhost:8000/docs)

---

## ✨ Features Implemented

- **🔐 JWT authentication and authorization** with roles: **Owner**, **Editor**, **Viewer**
- **📅 CRUD for events**:
  - Create, list (with pagination), get by ID, update, delete events
  - Batch creation of events
- **🔁 Recurring events** support:
  - `is_recurring`, `recurrence_pattern` fields with validation
- **⏰ Time conflict (overlap) detection** for events
- **🔗 Granular permissions/sharing**:
  - Grant/revoke/view roles per event
  - Endpoints for managing event permissions (`share`, `permissions` management)
- **📢 Real-time notifications**:
  - WebSocket notifications on permission changes
  - E2E WebSocket test included
- **📝 Event history, versioning, rollback**:
  - View event history (changelog)
  - View any past version
  - Rollback to a previous version
  - Get JSON diff between any two versions
- **📝 API documentation**:
  - Full OpenAPI docs available by default (`/docs`)
- **🛡️ Validation, error handling, security**:
  - Pydantic-based validation
  - Custom exception system, global error handlers
  - Rate limiting (SlowAPI)
  - Role- and permission-based access control for endpoints
- **⚡ MessagePack support** via Accept-header negotiation
- **📂 Logging** to file (app, audit, security logs)
- **📬 Postman collection** for all endpoints (see `tests/MyApp Tests.postman_collection.json`)
- **🧪 E2E test for notification system** (`tests/test_notifications.py`)
- **🐳 Docker & docker-compose** for easy environment setup
- **🧹 Pre-commit, flake8, black, CI pipeline** out of the box

---

## 🛠️ Tech Stack

- Python 3.10+
- FastAPI
- SQLAlchemy (async)
- Alembic (migrations)
- PostgreSQL
- Redis
- Docker, docker-compose
- WebSockets (starlette)
- Pre-commit, Flake8, Black
- Pytest, httpx, websockets (testing)
- MessagePack

---

## 📋 Task Checklist

| Feature                        | Status   |
|--------------------------------|----------|
| JWT Auth, Roles (Owner etc)    | ✅ Done  |
| CRUD Events, Pagination        | ✅ Done  |
| Recurring Events               | ✅ Done  |
| Overlap Detection              | ✅ Done  |
| Permissions Sharing            | ✅ Done  |
| WebSocket Notifications        | ✅ Done  |
| History, Rollback, Diff        | ✅ Done  |
| OpenAPI Docs                   | ✅ Done  |
| Validation, Rate Limit, Errors | ✅ Done  |
| MessagePack support            | ✅ Done  |
| Docker / Compose               | ✅ Done  |
| E2E Test                       | ✅ Done  |
| Postman Collection             | ✅ Done  |

---

## 📦 Project Structure

<details>
<summary>Click to expand</summary>

```
.
├── .env
├── .env.example
├── .flake8
├── .pre-commit-config.yaml
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── README.md
├── alembic/
├── app/
│   ├── api/
│   ├── core/
│   ├── db/
│   ├── main.py
│   ├── models/
│   ├── schemas/
│   ├── services/
│   └── utils/
├── logs/
├── requirements.txt
├── requirements-dev.txt
└── tests/
    ├── MyApp Tests.postman_collection.json
    ├── test_notifications.py
    └── test_smoke.py
```
</details>

---

## ⚙️ Environment Configuration

Create a `.env` file based on `.env.example`:
```ini
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/eventdb
DATABASE_URL_LOCAL=postgresql+psycopg2://postgres:postgres@localhost:5432/eventdb
REDIS_URL=redis://redis:6379/0
ACCESS_TOKEN_SECRET=your_super_secret_key
REFRESH_TOKEN_SECRET=my_super_secret_key
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=eventdb
PGADMIN_DEFAULT_EMAIL=admin@admin.com
PGADMIN_DEFAULT_PASSWORD=admin123
```

---

## 🚀 Getting Started

### Prerequisites

- **Docker** and **docker-compose** installed locally.

### Running the Application

Build and start all services:
```bash
docker-compose up --build
```

- The API will be available at `http://localhost:8000`
- Swagger/OpenAPI docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Running Database Migrations

```bash
alembic upgrade head
```

### Pre-commit Hooks

Install pre-commit hooks (optional, for local development):

```bash
pre-commit install
```

---

## 🧪 Testing

### E2E Tests

The project includes an **end-to-end (e2e) test** for WebSocket notifications (see: `tests/test_notifications.py`).  
To run e2e tests (from within the container or locally with a proper environment):

```bash
export RUN_E2E_TESTS=1
pytest tests/test_notifications.py
```

### Postman Collection

- Import the provided `tests/MyApp Tests.postman_collection.json` into Postman.
- All API endpoints are covered with example requests, including authentication, event CRUD, permissions, versioning, rollback, and notifications.
- Use the `/api/auth/register` and `/api/auth/login` endpoints first to get a valid access token.

---

## 🗂 RBAC (Roles and Permissions)

- **Owner**: Full access to all event operations, permission management, versioning.
- **Editor**: Can edit event and manage content, but not sharing/ownership.
- **Viewer**: Read-only access to event details.

---

## 📚 API Endpoints (Implemented)

- `POST /api/auth/register`, `POST /api/auth/login`
- `GET /api/events` (with pagination)
- `POST /api/events`, `POST /api/events/batch`
- `GET /api/events/{id}`
- `PUT /api/events/{id}`
- `DELETE /api/events/{id}`
- `POST /api/events/{id}/share`
- `GET /api/events/{id}/permissions`
- `PUT /api/events/{id}/permissions/{userId}`
- `DELETE /api/events/{id}/permissions/{userId}`
- `GET /api/events/{id}/history`
- `GET /api/events/{id}/history/{versionId}`
- `POST /api/events/{id}/rollback/{versionId}`
- `GET /api/events/{id}/diff/{versionId1}/{versionId2}`
- WebSocket endpoint: `/api/ws/notifications`

(See full documentation at `/docs`)

---

## 🛡️ Security

- JWT authentication, custom error handling, and security logging.
- Rate limiting: 200 requests/minute per client.
- All endpoints protected by roles and permissions.
- WebSocket authentication via Bearer token.

---

## 📈 Test Coverage

- e2e (end-to-end) test for real-time notifications
- Postman collection for manual/automated API checks

> Note: Unit tests for business logic can be added as next step.

---

## 📝 Logging

- Application logs, audit logs, and security logs are written to `/logs` (mounted as a Docker volume).
- All major actions (auth, CRUD, permissions, notifications) are logged.

---

## 🤝 Contributions

Open to contributions — just fork and PR!

---

## 👤 Author

[Georgii Kutin](https://github.com/irefuse3585)

---

Task: https://docs.google.com/document/d/1kPhppih_OrYvj_dzzoJIfw6KUL6oK-J35G3z9lc-ois/edit?tab=t.0#heading=h.h8bj1c7g648k

## 📄 License

MIT

