"""
消息总线 - Agent 间通信基础设施

核心功能：
1. 消息发布和订阅
2. 消息路由
3. 请求-响应模式
4. 异步处理
"""

from typing import Dict, Any, Callable, Optional, List
import asyncio
import logging
from enum import Enum
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """消息类型"""
    AGENT_REQUEST = "agent_request"
    AGENT_RESPONSE = "agent_response"
    AGENT_FEEDBACK = "agent_feedback"
    AGENT_BROADCAST = "agent_broadcast"
    TASK_UPDATE = "task_update"
    TREND_UPDATE = "trend_update"


class Message(Dict[str, Any]):
    """消息对象"""

    def __init__(
        self,
        message_type: MessageType,
        topic: str,
        payload: Dict[str, Any],
        sender: Optional[str] = None
    ):
        super().__init__()
        self["type"] = message_type.value
        self["topic"] = topic
        self["payload"] = payload
        self["sender"] = sender
        self["timestamp"] = datetime.now().isoformat()
        self["message_id"] = f"msg_{datetime.now().timestamp()}"


class MessageBus:
    """消息总线

    支持：
    1. 点对点通信
    2. 发布订阅
    3. 消息路由
    4. 异步处理

    注意：当前实现为内存版本，生产环境可替换为 RabbitMQ/Kafka
    """

    def __init__(self, broker_url: str = "memory://localhost"):
        """初始化消息总线

        Args:
            broker_url: 消息代理 URL（当前仅支持 memory://）
        """
        self.broker_url = broker_url
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self.pending_responses: Dict[str, asyncio.Future] = {}
        self._running = False

        logger.info(f"MessageBus initialized with broker: {broker_url}")

    async def start(self):
        """启动消息总线"""
        self._running = True
        logger.info("MessageBus started")

    async def stop(self):
        """停止消息总线"""
        self._running = False
        # 取消所有待处理的响应
        for future in self.pending_responses.values():
            if not future.done():
                future.cancel()
        logger.info("MessageBus stopped")

    async def publish(
        self,
        topic: str,
        payload: Dict[str, Any],
        message_type: MessageType = MessageType.AGENT_REQUEST,
        sender: Optional[str] = None
    ):
        """发布消息

        Args:
            topic: 主题
            payload: 消息内容
            message_type: 消息类型
            sender: 发送者
        """
        message = Message(
            message_type=message_type,
            topic=topic,
            payload=payload,
            sender=sender
        )

        logger.debug(f"Publishing message to topic: {topic}, type: {message_type}")

        # 通知所有订阅者
        if topic in self.subscribers:
            tasks = []
            for callback in self.subscribers[topic]:
                tasks.append(self._safe_callback(callback, message))

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_callback(self, callback: Callable, message: Dict[str, Any]):
        """安全执行回调函数"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(message)
            else:
                callback(message)
        except Exception as e:
            logger.error(f"Error in callback: {e}", exc_info=True)

    async def subscribe(
        self,
        topic: str,
        callback: Callable
    ):
        """订阅主题

        Args:
            topic: 主题
            callback: 回调函数
        """
        self.subscribers[topic].append(callback)
        logger.info(f"Subscribed to topic: {topic}")

    async def unsubscribe(
        self,
        topic: str,
        callback: Callable
    ):
        """取消订阅

        Args:
            topic: 主题
            callback: 回调函数
        """
        if topic in self.subscribers and callback in self.subscribers[topic]:
            self.subscribers[topic].remove(callback)
            logger.info(f"Unsubscribed from topic: {topic}")

    async def request_response(
        self,
        target_agent: str,
        request: Dict[str, Any],
        timeout: int = 30,
        sender: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """请求-响应模式

        Args:
            target_agent: 目标 Agent
            request: 请求内容
            timeout: 超时时间（秒）
            sender: 发送者

        Returns:
            响应内容
        """
        # 生成请求 ID
        request_id = f"req_{datetime.now().timestamp()}"

        # 创建响应 Future
        response_future = asyncio.Future()
        self.pending_responses[request_id] = response_future

        # 订阅响应
        response_topic = f"response.{target_agent}.{request_id}"

        async def response_handler(message: Dict[str, Any]):
            payload = message["payload"]
            if payload.get("request_id") == request_id:
                if not response_future.done():
                    response_future.set_result(payload)

        await self.subscribe(response_topic, response_handler)

        # 发送请求
        await self.publish(
            f"request.{target_agent}",
            {
                "request_id": request_id,
                "content": request,
                "response_topic": response_topic
            },
            MessageType.AGENT_REQUEST,
            sender=sender
        )

        # 等待响应
        try:
            response = await asyncio.wait_for(response_future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            logger.error(f"Request to {target_agent} timed out after {timeout}s")
            return None
        finally:
            # 清理
            await self.unsubscribe(response_topic, response_handler)
            self.pending_responses.pop(request_id, None)

    async def broadcast(
        self,
        payload: Dict[str, Any],
        sender: Optional[str] = None
    ):
        """广播消息给所有 Agent

        Args:
            payload: 消息内容
            sender: 发送者
        """
        await self.publish(
            "broadcast.all",
            payload,
            MessageType.AGENT_BROADCAST,
            sender=sender
        )

    def get_stats(self) -> Dict[str, Any]:
        """获取消息总线统计信息

        Returns:
            统计信息
        """
        return {
            "running": self._running,
            "total_topics": len(self.subscribers),
            "total_subscribers": sum(len(subs) for subs in self.subscribers.values()),
            "pending_responses": len(self.pending_responses),
            "topics": list(self.subscribers.keys())
        }
