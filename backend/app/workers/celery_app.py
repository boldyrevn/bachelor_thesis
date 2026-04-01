"""Celery application configuration."""

from celery import Celery

from app.core.config import settings


def create_celery_app() -> Celery:
    """Create and configure Celery application."""
    celery_app = Celery(
        "flowforge",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
        include=[
            "app.workers.tasks",
        ],
    )

    celery_app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=3600,  # 1 hour max
        task_soft_time_limit=3300,  # 55 minutes soft limit
    )

    return celery_app


celery_app = create_celery_app()
