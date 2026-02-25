"""
WebSocket 模块初始化
"""

from app.shared.websocket.manager import (
    manager,
    push_task_status,
    push_crawl_progress,
    push_analysis_progress,
    push_generation_result,
    push_grpo_training_update,
    push_system_alert,
    push_metrics_update
)

from app.shared.websocket.routes import router as websocket_router

__all__ = [
    # 管理器
    'manager',

    # 推送函数
    'push_task_status',
    'push_crawl_progress',
    'push_analysis_progress',
    'push_generation_result',
    'push_grpo_training_update',
    'push_system_alert',
    'push_metrics_update',

    # 路由
    'websocket_router'
]
