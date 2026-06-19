# Fujikura Project

## Technical Description

This project implements a backend service for applicator management and tracking within predefined zones and machines. The architecture adheres to principles of Clean Architecture and Command Query Responsibility Segregation (CQRS). It enforces strict layer separation, mapping presentation elements, domain logic, and infrastructure details independently.

The application relies on:
- **Presentation Layer:** FastAPI for handling HTTP and WebSocket requests.
- **Application Layer:** Command and Query Handlers orchestrating domain models and infrastructure services.
- **Domain Layer:** Pure Python classes defining entities (Applicators, Machines, Zones, Users, MovementLogs, BlockLogs), enums (Role, ApplicatorState), and custom domain exceptions (EntityNotFoundError, ConcurrencyError, DuplicateEntityError, InvalidStateError).
- **Infrastructure Layer:** SQLAlchemy ORM for relational data mapping, Alembic for schema migrations, and Dishka for Dependency Injection / Inversion of Control (IoC).

### Key Architectural Patterns
- **CQRS:** Read and write operations are strictly segregated. Commands manipulate state through Unit of Work and Repositories, while Queries bypass repositories and read directly via QueryServices to optimized Data Transfer Objects (DTOs).
- **Unit of Work (UoW):** Ensures atomic transactions across multiple repository operations.
- **Optimistic Concurrency Control:** Enforced at the domain and repository level utilizing a `version` field to prevent race conditions during concurrent modifications.
- **Inversion of Control:** Dishka container manages the lifecycle and provisioning of all handlers, UoW instances, and database sessions.

---

## Setup Instructions

### 1. Prerequisites
- Python 3.10+
- Docker and Docker Compose (if deploying via containers)
- SQLite (for local development) or PostgreSQL

### 2. Local Environment Setup

Create a virtual environment and install dependencies:

```bash
python -m venv venv
# On Windows
venv\Scripts\activate
# On Unix or MacOS
source venv/bin/activate

pip install -r requirements.txt
# Alternatively, if using pdm/poetry, initialize via the corresponding package manager
```

### 3. Database Initialization

The project utilizes Alembic for database migrations. To initialize or update your schema:

```bash
alembic upgrade head
```

To seed the database with initial required data (e.g., standard users, initial zones):

```bash
python seed.py
```

### 4. Running the Application

To start the FastAPI server via Uvicorn:

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

### 5. Running via Docker

The repository includes a `docker-compose.yml` defining the API backend, the database, and any necessary supporting services (e.g., Nginx for the frontend).

```bash
docker-compose up -d --build
```

### 6. Running Tests

The test suite is structured into unit tests and integration tests. Pytest is the designated test runner.

```bash
pytest
```