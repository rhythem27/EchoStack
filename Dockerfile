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

# Install build dependencies, libpq (for Postgres), and libraries for document parsing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    libgomp1 \
    libgl1 \
    libglib2.0-0 \
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
    PATH="/app/.venv/bin:$PATH"

# Install runtime utilities (libpq for postgres, libraries for document processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgomp1 \
    libgl1 \
    libglib2.0-0 \
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
