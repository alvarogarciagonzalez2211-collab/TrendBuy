import os

from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv


load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery(
    "trendbuy",
    broker=REDIS_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["services.tasks"],
)

celery_app.conf.update(
    timezone="Europe/Madrid",
    enable_utc=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    beat_schedule={
        "scrape-prices-every-12-hours": {
            "task": "services.tasks.scrape_prices",
            "schedule": crontab(hour="*/12", minute=0),
        },
    },
)
