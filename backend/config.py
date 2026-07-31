import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

class Settings(BaseSettings):
    APP_ENV: str = os.getenv("APP_ENV", "development")
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")

    # PostgreSQL Database URL
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # Redis Connection URL
    REDIS_URL: str = os.getenv("REDIS_URL", "")

    # Apache Kafka Broker configuration
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:9092")
    KAFKA_INGESTION_TOPIC: str = os.getenv("KAFKA_INGESTION_TOPIC", "document.ingestion.events")

    # Ingestion configurations
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "/tmp/uploads")

    # Gemini Live Configuration
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_LIVE_MODEL: str = os.getenv("GEMINI_LIVE_MODEL", "gemini-3.1-flash-live-preview")

    # Super Admin Configuration
    SUPER_ADMIN_EMAIL: str = os.getenv("SUPER_ADMIN_EMAIL", "")
    SUPER_ADMIN_PASSWORD: str = os.getenv("SUPER_ADMIN_PASSWORD", "")
    SUPER_ADMIN_ID: str = os.getenv("SUPER_ADMIN_ID", "echo-admin")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
