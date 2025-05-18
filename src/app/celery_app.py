from celery import Celery
from .config import settings

celery_app = Celery(
    "fitbot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.app.tasks"]
)

# Optional configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
) 