"""
Celery beat scheduler — runs daily pipeline automatically.
Start worker:  celery -A app.tasks worker --loglevel=info
Start beat:    celery -A app.tasks beat --loglevel=info
"""
from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "pibprep",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.timezone = "Asia/Kolkata"

celery_app.conf.beat_schedule = {
    # Run PIB ingestion every day at 6:30 AM IST
    "ingest-pib-daily": {
        "task": "app.tasks.ingest_pib",
        "schedule": crontab(hour=6, minute=30),
    },
    # Generate MCQs at 7:00 AM IST (after ingestion completes)
    "generate-mcqs-daily": {
        "task": "app.tasks.generate_mcqs",
        "schedule": crontab(hour=7, minute=0),
    },
}

@celery_app.task(name="app.tasks.ingest_pib", bind=True, max_retries=3)
def ingest_pib(self):
    import asyncio
    try:
        from app.services.ingestion import ingest
        asyncio.run(ingest())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * 5)

@celery_app.task(name="app.tasks.generate_mcqs", bind=True, max_retries=2)
def generate_mcqs(self):
    import asyncio
    try:
        from app.services.mcq_generator import run_generator
        asyncio.run(run_generator())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * 10)
