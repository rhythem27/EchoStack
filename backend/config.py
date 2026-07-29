import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

class Settings(BaseSettings):
    APP_ENV: str = "development"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    SECRET_KEY: str = "dev_secret_jwt_sign_key_98374591"

    # PostgreSQL Database URL
    DATABASE_URL: str = "postgresql://postgres_user:postgres_secure_password@localhost:5432/echostack_db"

    # Redis Connection URL
    REDIS_URL: str = "redis://localhost:6379/0"

    # Apache Kafka Broker configuration
    KAFKA_BOOTSTRAP_SERVERS: str = "127.0.0.1:9092"
    KAFKA_INGESTION_TOPIC: str = "document.ingestion.events"

    # Ingestion configurations
    UPLOAD_DIR: str = "/tmp/uploads"

    # Gemini Live Configuration
    GEMINI_API_KEY: str = ""
    GEMINI_LIVE_MODEL: str = "gemini-2.0-flash-exp"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
