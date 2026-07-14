# ==============================================================================
# Multi-Stage Dockerfile for EchoStack FastAPI Core Engine
# ==============================================================================

# --- Stage 1: Build Environment ---
FROM python:3.11-slim as builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

# Install build dependencies, libpq (for Postgres), and java (runtime dependency for PySpark client)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Add Poetry to PATH
ENV PATH="$POETRY_HOME/bin:$PATH"

WORKDIR /app

# Copy dependency definition files first (this leverages Docker layer caching)
COPY pyproject.toml poetry.lock* ./

# Resolve and install production dependencies (excluding dev packages)
# If poetry.lock is missing, it will generate it. We create a placeholder if lock does not exist.
RUN if [ -f poetry.lock ]; then \
        poetry install --only main --no-root; \
    else \
        poetry install --only main --no-root --no-directory; \
    fi

# --- Stage 2: Runtime Environment ---
FROM python:3.11-slim as runner

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    JAVA_HOME="/usr/lib/jvm/java-17-openjdk-amd64" \
    PATH="/app/.venv/bin:$PATH"

# Install runtime utilities (libpq for postgres, openjdk for local Spark driver operations)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    openjdk-17-jre-headless \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the virtual environment built in the builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy local application code into runtime container
COPY . /app

EXPOSE 8000

# Run FastAPI app with Uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
