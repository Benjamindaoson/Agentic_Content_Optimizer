"""
Celery 任务队列配置

用于处理长时间运行的后台任务
"""

from celery import Celery
from kombu import Queue
from celery.schedules import crontab
import os

# Celery 配置
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# 创建 Celery 应用
celery_app = Celery(
    'viral_flywheel',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.tasks",
        "app.tasks.tasks_v4",
        "app.tasks.training_tasks",
        "app.tasks.scheduled_tasks",
    ],
)

# Celery 配置
celery_app.conf.update(
    # 任务序列化
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,

    # 任务路由
    task_routes={
        'app.tasks.crawl.*': {'queue': 'crawl'},
        'app.tasks.analyze.*': {'queue': 'analyze'},
        'app.tasks.generate.*': {'queue': 'generate'},
        'app.tasks.grpo.*': {'queue': 'grpo'},
    },

    # 任务队列
    task_queues=(
        Queue('default', routing_key='default'),
        Queue('crawl', routing_key='crawl'),
        Queue('analyze', routing_key='analyze'),
        Queue('generate', routing_key='generate'),
        Queue('grpo', routing_key='grpo'),
    ),

    # 任务优先级
    task_default_priority=5,
    task_queue_max_priority=10,

    # 任务超时
    task_soft_time_limit=3600,  # 1 小时软超时
    task_time_limit=7200,  # 2 小时硬超时

    # 任务重试
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # 结果过期时间
    result_expires=86400,  # 24 小时

    # Worker 配置
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,

    # 任务追踪
    task_track_started=True,
    task_send_sent_event=True,
)

# 生产级基础调度（与其他模块 update 合并，不覆盖）
celery_app.conf.beat_schedule = celery_app.conf.get('beat_schedule', {}) or {}
celery_app.conf.beat_schedule.update({
    # 每 6 小时：自动采集和 RL 同步
    'system-auto-scrape-outcomes-6h': {
        'task': 'app.tasks.system.auto_scrape_outcomes',
        'schedule': crontab(minute=0, hour='*/6'),
    },
    'system-sync-outcomes-to-rl-6h': {
        'task': 'app.tasks.system.sync_outcomes_to_rl',
        'schedule': crontab(minute=10, hour='*/6'),
    },
    # 每 5 分钟：监控告警派发
    'system-dispatch-monitor-alerts-5m': {
        'task': 'app.tasks.system.dispatch_monitor_alerts',
        'schedule': crontab(minute='*/5'),
    },
    # 每日清理图谱历史
    'system-prune-graph-store-daily': {
        'task': 'app.tasks.system.prune_graph_store',
        'schedule': crontab(hour=3, minute=0),
        'args': (30,),
    },
})


# 任务装饰器
def task(*args, **kwargs):
    """Celery 任务装饰器"""
    kwargs.setdefault('bind', True)
    kwargs.setdefault('max_retries', 3)
    kwargs.setdefault('default_retry_delay', 60)
    return celery_app.task(*args, **kwargs)
