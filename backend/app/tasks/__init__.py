"""任务模块初始化。

保持轻量导入，避免因为历史模块依赖导致 Celery 启动失败。
任务注册由 celery_config.Celery(include=[...]) 完成。
"""

from app.tasks.celery_config import celery_app, task

__all__ = ["celery_app", "task"]
