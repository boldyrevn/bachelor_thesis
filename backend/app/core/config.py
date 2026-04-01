"""Core configuration for FlowForge backend."""

import logging
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "FlowForge"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://flowforge:flowforge_secret@localhost:5432/flowforge"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # MinIO / S3
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "flowforge_admin"
    MINIO_SECRET_KEY: str = "flowforge_secret"
    MINIO_SECURE: bool = False

    # Spark
    SPARK_MASTER: str = "spark://localhost:7077"

    @property
    def minio_url(self) -> str:
        """Get MinIO URL with scheme."""
        scheme = "https" if self.MINIO_SECURE else "http"
        return f"{scheme}://{self.MINIO_ENDPOINT}"

    def get_celery_config(self) -> dict[str, Any]:
        """Get Celery configuration dictionary."""
        return {
            "broker_url": self.CELERY_BROKER_URL,
            "result_backend": self.CELERY_RESULT_BACKEND,
            "task_serializer": "json",
            "result_serializer": "json",
            "accept_content": ["json"],
            "timezone": "UTC",
            "enable_utc": True,
        }


def setup_logging(debug: bool = False) -> None:
    """Configure JSON logging for the application."""
    log_level = logging.DEBUG if debug else logging.INFO

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)

    # Silence noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


# Global settings instance
settings = Settings()
