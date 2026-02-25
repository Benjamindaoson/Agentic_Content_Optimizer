"""生产调度任务注册（Celery beat 使用）。"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict

from celery.schedules import crontab

from app.engine.rag.graph_store import GraphStore
from app.tasks.celery_config import celery_app, task
from app.tasks.monitoring_tasks import dispatch_monitor_alerts_task
from app.tasks.outcome_sync_tasks import auto_scrape_outcomes_task, sync_outcomes_to_rl_task


def _run_async(coro):
    try:
        with asyncio.Runner() as runner:
            return runner.run(coro)
    except AttributeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


@task(name="app.tasks.system.auto_scrape_outcomes")
def auto_scrape_outcomes_celery_task() -> Dict[str, Any]:
    return auto_scrape_outcomes_task()


@task(name="app.tasks.system.sync_outcomes_to_rl")
def sync_outcomes_to_rl_celery_task() -> Dict[str, Any]:
    return sync_outcomes_to_rl_task()


@task(name="app.tasks.system.dispatch_monitor_alerts")
def dispatch_monitor_alerts_celery_task() -> Dict[str, Any]:
    return dispatch_monitor_alerts_task()


@task(name="app.tasks.system.prune_graph_store")
def prune_graph_store_task(max_age_days: int = 30) -> Dict[str, Any]:
    store = GraphStore()
    result = _run_async(store.prune_stale_data(max_age_days=max_age_days))
    return {
        "success": True,
        "timestamp": datetime.utcnow().isoformat(),
        **result,
    }


# Beat 任务：增量合并，不覆盖已有调度
celery_app.conf.beat_schedule = celery_app.conf.get("beat_schedule", {}) or {}
celery_app.conf.beat_schedule.update(
    {
        # 每 6 小时：自动采集 -> RL 同步
        "auto-scrape-outcomes-6h": {
            "task": "app.tasks.system.auto_scrape_outcomes",
            "schedule": crontab(minute=0, hour="*/6"),
        },
        "sync-outcomes-to-rl-6h": {
            "task": "app.tasks.system.sync_outcomes_to_rl",
            "schedule": crontab(minute=10, hour="*/6"),
        },
        # 每 5 分钟：派发监控告警
        "dispatch-monitor-alerts-5m": {
            "task": "app.tasks.system.dispatch_monitor_alerts",
            "schedule": crontab(minute="*/5"),
        },
        # 每天凌晨 3 点：清理 30 天前图谱历史
        "prune-graph-store-daily": {
            "task": "app.tasks.system.prune_graph_store",
            "schedule": crontab(hour=3, minute=0),
            "args": (30,),
        },
    }
)

