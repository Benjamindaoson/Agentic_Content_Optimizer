"""
Celery tasks for automated training pipeline.
"""

from celery import Celery
from celery.schedules import crontab
import asyncio
from datetime import datetime

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.training.data_collection.real_data_collector import RealDataCollector
from app.training.grpo_training_loop_mvp import GRPOTrainingLoopMVP

settings = get_settings()

# Initialize Celery
celery_app = Celery(
    "growth_flywheel",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3000,  # 50 minutes
)


def run_async(coro):
    """Helper to run async functions in Celery tasks."""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@celery_app.task(name="collect_viral_notes", queue="crawl")
def collect_viral_notes_task(
    category: str = "美妆",
    target_count: int = 100,
    min_likes: int = 10000
):
    """
    Scheduled task to collect viral notes.
    Runs daily to gather new training data.
    """
    async def _collect():
        async with AsyncSessionLocal() as db:
            collector = RealDataCollector(db, use_real_crawler=False)  # Use mock for now
            result = await collector.collect_viral_notes(
                category=category,
                target_count=target_count,
                min_likes=min_likes
            )
            return result

    result = run_async(_collect())
    return {
        "task": "collect_viral_notes",
        "timestamp": datetime.now().isoformat(),
        "result": result
    }


@celery_app.task(name="run_grpo_training", queue="training")
def run_grpo_training_task(min_samples: int = 50):
    """
    Scheduled task to run GRPO training.
    Runs daily after data collection.
    """
    async def _train():
        async with AsyncSessionLocal() as db:
            trainer = GRPOTrainingLoopMVP(db)
            result = await trainer.run_training_episode()
            return result

    result = run_async(_train())
    return {
        "task": "run_grpo_training",
        "timestamp": datetime.now().isoformat(),
        "result": result
    }


@celery_app.task(name="collect_online_metrics", queue="crawl")
def collect_online_metrics_task():
    """
    Scheduled task to collect metrics for published content.
    Runs hourly to update performance data.
    """
    # TODO: Implement online metrics collection
    return {
        "task": "collect_online_metrics",
        "timestamp": datetime.now().isoformat(),
        "status": "not_implemented"
    }


# Celery Beat Schedule
celery_app.conf.beat_schedule = {
    # Collect viral notes daily at 2 AM
    "collect-viral-notes-daily": {
        "task": "collect_viral_notes",
        "schedule": crontab(hour=2, minute=0),
        "args": ("美妆", 100, 10000),
    },
    # Run GRPO training daily at 4 AM (after data collection)
    "run-grpo-training-daily": {
        "task": "run_grpo_training",
        "schedule": crontab(hour=4, minute=0),
        "args": (50,),
    },
    # Collect online metrics every hour
    "collect-online-metrics-hourly": {
        "task": "collect_online_metrics",
        "schedule": crontab(minute=0),  # Every hour
    },
}


if __name__ == "__main__":
    # For testing tasks manually
    print("Testing Celery tasks...")

    # Test data collection
    print("\n1. Testing data collection...")
    result = collect_viral_notes_task.apply_async()
    print(f"Task ID: {result.id}")

    # Test training
    print("\n2. Testing GRPO training...")
    result = run_grpo_training_task.apply_async()
    print(f"Task ID: {result.id}")
