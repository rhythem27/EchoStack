import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_ENV: str = "development"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    SECRET_KEY: str = "dev_secret_jwt_sign_key_98374591"

    # PostgreSQL Database URL
    DATABASE_URL: str = "postgresql://postgres_user:postgres_secure_password@postgres:5432/echostack_db"

    # Redis Connection URL
    REDIS_URL: str = "redis://redis:6379/0"

    # Apache Kafka Broker configuration
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_INGESTION_TOPIC: str = "document.ingestion.events"

    # Ingestion configurations
    UPLOAD_DIR: str = "/tmp/uploads"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
