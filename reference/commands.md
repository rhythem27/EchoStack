# operational & Development Commands Reference

This document provides a catalog of CLI commands used to run, build, test, and manage the EchoStack project.

---

## 1. Docker & Infrastructure Service Management

These commands run, manage, and shut down the containerized infrastructure (Postgres, Redis, Kafka).

### Start Services (Detached Mode)
```bash
docker compose up -d
```

### Stop and Clean Services
```bash
docker compose down
```

### Check Container Status
```bash
docker compose ps
```

### Inspect Container Logs
```bash
docker compose logs -f [service_name]
```
*(e.g., `docker compose logs -f postgres`)*

---

## 2. Dependency Management via Poetry

These commands manage packages, generate locks, and initialize virtual environments.

### Resolve and Lock Dependencies
```bash
poetry lock
```

### Install Dependencies
```bash
poetry install
```

### Activate the Poetry Virtual Environment Shell
```bash
poetry shell
```

---

## 3. Backend Microservices Execution (Local Development)

These commands run the individual Python application modules locally (assuming dependencies are installed via Poetry).

### Run FastAPI Ingress / Core API Gateway (Uvicorn)
```bash
poetry run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Run Kafka Ingestion Document Processor (Worker)
```bash
poetry run python backend/worker.py
```

### Execute PySpark Batch Engagement Analysis (ETL Analytics Job)
```bash
poetry run python backend/analytics_job.py
```

---


