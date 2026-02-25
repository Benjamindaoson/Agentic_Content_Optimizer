"""
WebSocket 管理器

用于实时推送任务状态和系统事件
"""

from typing import Dict, Set, Any
from fastapi import WebSocket
import json
import asyncio
from datetime import datetime


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        # 活跃连接
        self.active_connections: Set[WebSocket] = set()

        # 订阅频道
        self.subscriptions: Dict[str, Set[WebSocket]] = {}

        # 基础保护
        self.max_connections: int = 200

    async def connect(self, websocket: WebSocket) -> bool:
        """接受新连接。返回是否成功连接。"""
        if len(self.active_connections) >= self.max_connections:
            await websocket.close(code=1013)  # Try again later
            return False
        await websocket.accept()
        self.active_connections.add(websocket)
        return True

    def disconnect(self, websocket: WebSocket):
        """断开连接"""
        self.active_connections.discard(websocket)

        # 从所有订阅中移除
        for channel in self.subscriptions.values():
            channel.discard(websocket)

    async def subscribe(self, websocket: WebSocket, channel: str):
        """订阅频道"""
        if channel not in self.subscriptions:
            self.subscriptions[channel] = set()

        self.subscriptions[channel].add(websocket)

    async def unsubscribe(self, websocket: WebSocket, channel: str):
        """取消订阅"""
        if channel in self.subscriptions:
            self.subscriptions[channel].discard(websocket)

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """发送个人消息"""
        try:
            await websocket.send_json(message)
        except:
            self.disconnect(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """广播消息给所有连接"""
        disconnected = set()

        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.add(connection)

        # 清理断开的连接
        for connection in disconnected:
            self.disconnect(connection)

    async def broadcast_to_channel(self, channel: str, message: Dict[str, Any]):
        """广播消息到指定频道"""
        if channel not in self.subscriptions:
            return

        disconnected = set()

        for connection in self.subscriptions[channel]:
            try:
                await connection.send_json(message)
            except:
                disconnected.add(connection)

        # 清理断开的连接
        for connection in disconnected:
            self.disconnect(connection)


# 全局连接管理器
manager = ConnectionManager()


# ==================== 事件推送函数 ====================

async def push_task_status(
    task_id: str,
    status: str,
    progress: float = None,
    message: str = None,
    data: Dict[str, Any] = None
):
    """
    推送任务状态

    Args:
        task_id: 任务 ID
        status: 状态（pending/running/completed/failed）
        progress: 进度（0-1）
        message: 消息
        data: 额外数据
    """
    event = {
        'type': 'task_status',
        'task_id': task_id,
        'status': status,
        'progress': progress,
        'message': message,
        'data': data,
        'timestamp': datetime.now().isoformat()
    }

    # 推送到任务频道
    await manager.broadcast_to_channel(f'task:{task_id}', event)

    # 推送到全局任务频道
    await manager.broadcast_to_channel('tasks', event)


async def push_crawl_progress(
    task_id: str,
    current: int,
    total: int,
    success: int,
    failed: int
):
    """
    推送采集进度

    Args:
        task_id: 任务 ID
        current: 当前数量
        total: 总数量
        success: 成功数量
        failed: 失败数量
    """
    progress = current / total if total > 0 else 0

    await push_task_status(
        task_id=task_id,
        status='running',
        progress=progress,
        message=f'采集进度: {current}/{total}',
        data={
            'current': current,
            'total': total,
            'success': success,
            'failed': failed
        }
    )


async def push_analysis_progress(
    task_id: str,
    current: int,
    total: int,
    note_id: str = None
):
    """
    推送分析进度

    Args:
        task_id: 任务 ID
        current: 当前数量
        total: 总数量
        note_id: 当前笔记 ID
    """
    progress = current / total if total > 0 else 0

    await push_task_status(
        task_id=task_id,
        status='running',
        progress=progress,
        message=f'分析进度: {current}/{total}',
        data={
            'current': current,
            'total': total,
            'note_id': note_id
        }
    )


async def push_generation_result(
    generation_id: str,
    title: str,
    hybrid_score: float,
    pattern_name: str
):
    """
    推送生成结果

    Args:
        generation_id: 生成 ID
        title: 标题
        hybrid_score: 混合分数
        pattern_name: 模式名称
    """
    event = {
        'type': 'generation_result',
        'generation_id': generation_id,
        'title': title,
        'hybrid_score': hybrid_score,
        'pattern_name': pattern_name,
        'timestamp': datetime.now().isoformat()
    }

    await manager.broadcast_to_channel('generations', event)


async def push_grpo_training_update(
    run_id: str,
    patterns_updated: int,
    avg_improvement: float,
    status: str
):
    """
    推送 GRPO 训练更新

    Args:
        run_id: 训练 ID
        patterns_updated: 更新模式数
        avg_improvement: 平均提升
        status: 状态
    """
    event = {
        'type': 'grpo_training',
        'run_id': run_id,
        'patterns_updated': patterns_updated,
        'avg_improvement': avg_improvement,
        'status': status,
        'timestamp': datetime.now().isoformat()
    }

    await manager.broadcast_to_channel('grpo', event)


async def push_system_alert(
    level: str,
    message: str,
    details: Dict[str, Any] = None
):
    """
    推送系统告警

    Args:
        level: 级别（info/warning/error）
        message: 消息
        details: 详情
    """
    event = {
        'type': 'system_alert',
        'level': level,
        'message': message,
        'details': details,
        'timestamp': datetime.now().isoformat()
    }

    await manager.broadcast_to_channel('alerts', event)
    await manager.broadcast(event)


async def push_metrics_update(
    metrics: Dict[str, Any]
):
    """
    推送指标更新

    Args:
        metrics: 指标数据
    """
    event = {
        'type': 'metrics_update',
        'metrics': metrics,
        'timestamp': datetime.now().isoformat()
    }

    await manager.broadcast_to_channel('metrics', event)
