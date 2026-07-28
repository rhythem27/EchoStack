# Script to start EchoStack Backend with local infrastructure overrides

$env:DATABASE_URL = "postgresql://postgres_user:postgres_secure_password@localhost:5432/echostack_db"
$env:REDIS_URL = "redis://localhost:6379/0"
$env:KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"

Write-Host "Starting EchoStack Backend API on http://127.0.0.1:8000..." -ForegroundColor Cyan
poetry run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
