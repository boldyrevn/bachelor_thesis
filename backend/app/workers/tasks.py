"""Celery task definitions."""

from app.workers.celery_app import celery_app


@celery_app.task(bind=True)
def example_task(self, x: int, y: int) -> int:
    """Example Celery task for testing."""
    return x + y
