"""
WebSocket 路由

提供 WebSocket 端点
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Any
import json

from app.shared.websocket.manager import manager
from app.core.database import AsyncSessionLocal
from sqlalchemy import select
from app.core.security import decode_token, verify_token_type
from app.models.user import User, UserRole


ALLOWED_CHANNELS_USER = {"workflow"}
ALLOWED_CHANNELS_ADMIN = {"workflow", "tasks", "generations", "grpo", "alerts", "metrics"}


async def _authenticate_ws(websocket: WebSocket) -> User:
    """WebSocket 鉴权：支持 ?token=xxx 或 Authorization: Bearer xxx"""
    token = websocket.query_params.get("token")
    if not token:
        auth = websocket.headers.get("authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()

    if not token:
        await websocket.close(code=1008)
        raise WebSocketDisconnect(code=1008)

    payload = decode_token(token)
    verify_token_type(payload, "access")
    user_id = payload.get("sub")
    if user_id is None:
        await websocket.close(code=1008)
        raise WebSocketDisconnect(code=1008)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            await websocket.close(code=1008)
            raise WebSocketDisconnect(code=1008)
        return user


def _can_subscribe(user: User, channel: str) -> bool:
    if channel.startswith("task:"):
        # 任务频道目前无任务归属校验数据，先允许登录用户订阅（后续可绑定 task->user_id）
        return True
    if user.role == UserRole.ADMIN:
        return channel in ALLOWED_CHANNELS_ADMIN
    return channel in ALLOWED_CHANNELS_USER


router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 主端点

    客户端可以发送订阅消息来订阅特定频道：
    {
        "action": "subscribe",
        "channel": "tasks"
    }

    支持的频道：
    - tasks: 所有任务状态
    - task:{task_id}: 特定任务状态
    - workflow: 工作流节点状态（workflow_status）
    - generations: 生成结果
    - grpo: GRPO 训练更新
    - alerts: 系统告警
    - metrics: 指标更新
    """
    user = await _authenticate_ws(websocket)
    ok = await manager.connect(websocket)
    if not ok:
        return

    try:
        # 简单消息速率限制（每连接每分钟最多 120 条）
        msg_times = []
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            # rate limit
            from time import time as _time
            now = _time()
            msg_times = [t for t in msg_times if now - t <= 60]
            if len(msg_times) >= 120:
                await websocket.close(code=1008)
                raise WebSocketDisconnect(code=1008)
            msg_times.append(now)

            try:
                message = json.loads(data)
                action = message.get('action')

                if action == 'subscribe':
                    # 订阅频道
                    channel = message.get('channel')
                    if channel:
                        if not _can_subscribe(user, channel):
                            await manager.send_personal_message(
                                {
                                    'type': 'subscription',
                                    'status': 'forbidden',
                                    'channel': channel,
                                    'message': '权限不足，无法订阅该频道'
                                },
                                websocket
                            )
                        else:
                            await manager.subscribe(websocket, channel)
                            await manager.send_personal_message(
                                {
                                    'type': 'subscription',
                                    'status': 'success',
                                    'channel': channel,
                                    'message': f'已订阅频道: {channel}'
                                },
                                websocket
                            )

                elif action == 'unsubscribe':
                    # 取消订阅
                    channel = message.get('channel')
                    if channel:
                        await manager.unsubscribe(websocket, channel)
                        await manager.send_personal_message(
                            {
                                'type': 'subscription',
                                'status': 'success',
                                'channel': channel,
                                'message': f'已取消订阅频道: {channel}'
                            },
                            websocket
                        )

                elif action == 'ping':
                    # 心跳
                    await manager.send_personal_message(
                        {
                            'type': 'pong',
                            'timestamp': message.get('timestamp')
                        },
                        websocket
                    )

                else:
                    await manager.send_personal_message(
                        {
                            'type': 'error',
                            'message': f'未知操作: {action}'
                        },
                        websocket
                    )

            except json.JSONDecodeError:
                await manager.send_personal_message(
                    {
                        'type': 'error',
                        'message': 'JSON 解析失败'
                    },
                    websocket
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.websocket("/ws/task/{task_id}")
async def task_websocket_endpoint(websocket: WebSocket, task_id: str):
    """
    任务专用 WebSocket 端点

    自动订阅特定任务的状态更新
    """
    user = await _authenticate_ws(websocket)
    ok = await manager.connect(websocket)
    if not ok:
        return
    await manager.subscribe(websocket, f'task:{task_id}')

    try:
        # 发送欢迎消息
        await manager.send_personal_message(
            {
                'type': 'connected',
                'task_id': task_id,
                'message': f'已连接到任务 {task_id} 的状态推送'
            },
            websocket
        )

        while True:
            # 保持连接，接收心跳
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                if message.get('action') == 'ping':
                    await manager.send_personal_message(
                        {
                            'type': 'pong',
                            'timestamp': message.get('timestamp')
                        },
                        websocket
                    )
            except:
                pass

    except WebSocketDisconnect:
        manager.disconnect(websocket)
