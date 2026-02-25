"""
增强的 Agent 通信系统

核心功能：
1. A2A 实时通信
2. 动态任务调整
3. 状态共享
4. 协同生成
"""

from typing import Dict, Any, Optional
import asyncio
import logging

from app.messaging.message_bus import MessageBus, MessageType
from app.engine.agents.base import BaseAgent, AgentResponse, AgentConfig

logger = logging.getLogger(__name__)


class EnhancedAgent(BaseAgent):
    """增强的 Agent 基类

    支持：
    1. A2A 通信
    2. 实时反馈
    3. 动态调整
    4. 消息订阅
    """

    def __init__(self, config: AgentConfig, message_bus: Optional[MessageBus] = None):
        super().__init__(config)
        self.message_bus = message_bus
        self._subscriptions = []

        if self.message_bus:
            # 异步设置订阅
            asyncio.create_task(self._setup_subscriptions())

    async def _setup_subscriptions(self):
        """设置消息订阅"""
        if not self.message_bus:
            return

        # 订阅针对本 Agent 的请求
        await self.message_bus.subscribe(
            f"request.{self.config.name}",
            self._handle_request
        )

        # 订阅反馈消息
        await self.message_bus.subscribe(
            f"feedback.{self.config.name}",
            self._handle_feedback
        )

        # 订阅广播消息
        await self.message_bus.subscribe(
            "broadcast.all",
            self._handle_broadcast
        )

        logger.info(f"{self.config.name} subscriptions set up")

    async def _handle_request(self, message: Dict[str, Any]):
        """处理请求消息"""
        try:
            request_id = message["payload"].get("request_id")
            content = message["payload"].get("content")
            response_topic = message["payload"].get("response_topic")

            logger.info(f"{self.config.name} received request: {request_id}")

            # 执行任务
            response = await self.execute(content)

            # 发送响应
            if response_topic and self.message_bus:
                await self.message_bus.publish(
                    response_topic,
                    {
                        "request_id": request_id,
                        "response": response.dict()
                    },
                    MessageType.AGENT_RESPONSE,
                    sender=self.config.name
                )

        except Exception as e:
            logger.error(f"{self.config.name} error handling request: {e}", exc_info=True)

    async def _handle_feedback(self, message: Dict[str, Any]):
        """处理反馈消息

        子类可以重写此方法来处理特定的反馈
        """
        feedback = message["payload"].get("feedback")
        sender = message.get("sender")

        logger.info(f"{self.config.name} received feedback from {sender}: {feedback}")

        # 子类可以根据反馈调整行为
        await self._process_feedback(feedback)

    async def _process_feedback(self, feedback: Dict[str, Any]):
        """处理反馈（子类可重写）

        Args:
            feedback: 反馈内容
        """
        pass

    async def _handle_broadcast(self, message: Dict[str, Any]):
        """处理广播消息"""
        logger.debug(f"{self.config.name} received broadcast: {message['payload']}")

    async def send_feedback(
        self,
        target_agent: str,
        feedback: Dict[str, Any]
    ):
        """发送反馈给其他 Agent

        Args:
            target_agent: 目标 Agent
            feedback: 反馈内容
        """
        if not self.message_bus:
            logger.warning(f"{self.config.name}: No message bus available")
            return

        await self.message_bus.publish(
            f"feedback.{target_agent}",
            {
                "from": self.config.name,
                "feedback": feedback
            },
            MessageType.AGENT_FEEDBACK,
            sender=self.config.name
        )

        logger.info(f"{self.config.name} sent feedback to {target_agent}")

    async def request_assistance(
        self,
        target_agent: str,
        request: Dict[str, Any],
        timeout: int = 30
    ) -> Optional[AgentResponse]:
        """请求其他 Agent 协助

        Args:
            target_agent: 目标 Agent
            request: 请求内容
            timeout: 超时时间

        Returns:
            Agent 响应
        """
        if not self.message_bus:
            logger.warning(f"{self.config.name}: No message bus available")
            return None

        logger.info(f"{self.config.name} requesting assistance from {target_agent}")

        response = await self.message_bus.request_response(
            target_agent,
            request,
            timeout=timeout,
            sender=self.config.name
        )

        if response:
            return AgentResponse(**response["response"])

        return None

    async def broadcast_update(self, update: Dict[str, Any]):
        """广播更新给所有 Agent

        Args:
            update: 更新内容
        """
        if not self.message_bus:
            logger.warning(f"{self.config.name}: No message bus available")
            return

        await self.message_bus.broadcast(
            {
                "from": self.config.name,
                "update": update
            },
            sender=self.config.name
        )

        logger.info(f"{self.config.name} broadcasted update")

    async def cleanup(self):
        """Properly clean up: unsubscribe from all topics and clear message queues."""
        if self.message_bus:
            topics_to_unsubscribe = [
                f"request.{self.config.name}",
                f"feedback.{self.config.name}",
                "broadcast.all",
            ]
            for topic in topics_to_unsubscribe:
                try:
                    if hasattr(self.message_bus, 'unsubscribe'):
                        await self.message_bus.unsubscribe(topic, self.config.name)
                    elif hasattr(self.message_bus, 'subscribers'):
                        subs = self.message_bus.subscribers.get(topic, {})
                        subs.pop(self.config.name, None)
                except Exception as e:
                    logger.debug(f"Unsubscribe from {topic} failed: {e}")

        # Clear any pending messages in the queue
        if hasattr(self, 'message_queue'):
            while not self.message_queue.empty():
                try:
                    self.message_queue.get_nowait()
                except Exception:
                    break

        logger.info(f"{self.config.name} cleaned up")
