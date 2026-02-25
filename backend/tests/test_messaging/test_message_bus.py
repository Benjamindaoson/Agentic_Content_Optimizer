"""
MessageBus 单元测试

测试消息总线的核心功能：
1. 消息发布和订阅
2. 请求-响应模式
3. 广播功能
4. 超时处理
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.messaging.message_bus import MessageBus, MessageType


class TestMessageBusInitialization:
    """测试消息总线初始化"""

    def test_default_initialization(self):
        """测试默认初始化"""
        bus = MessageBus()

        assert bus.broker_url == "memory://localhost"
        assert len(bus.subscribers) == 0
        assert len(bus.pending_responses) == 0

    def test_custom_initialization(self):
        """测试自定义初始化"""
        bus = MessageBus(broker_url="amqp://localhost:5672")

        assert bus.broker_url == "amqp://localhost:5672"


class TestMessageBusPublishSubscribe:
    """测试发布订阅功能"""

    @pytest.mark.asyncio
    async def test_publish_and_subscribe(self):
        """测试发布和订阅"""
        bus = MessageBus()
        await bus.start()

        received_messages = []

        async def callback(message):
            received_messages.append(message)

        # 订阅
        await bus.subscribe("test.topic", callback)

        # 发布
        await bus.publish(
            "test.topic",
            {"data": "test message"},
            MessageType.AGENT_REQUEST
        )

        # 等待消息处理
        await asyncio.sleep(0.1)

        assert len(received_messages) == 1
        assert received_messages[0]["topic"] == "test.topic"
        assert received_messages[0]["payload"]["data"] == "test message"

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        """测试多个订阅者"""
        bus = MessageBus()
        await bus.start()

        received_count = [0, 0]

        async def callback1(message):
            received_count[0] += 1

        async def callback2(message):
            received_count[1] += 1

        # 订阅
        await bus.subscribe("test.topic", callback1)
        await bus.subscribe("test.topic", callback2)

        # 发布
        await bus.publish("test.topic", {"data": "test"})

        # 等待消息处理
        await asyncio.sleep(0.1)

        assert received_count[0] == 1
        assert received_count[1] == 1

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        """测试取消订阅"""
        bus = MessageBus()
        await bus.start()

        received_messages = []

        async def callback(message):
            received_messages.append(message)

        # 订阅
        await bus.subscribe("test.topic", callback)

        # 发布第一条消息
        await bus.publish("test.topic", {"data": "message1"})
        await asyncio.sleep(0.1)

        # 取消订阅
        await bus.unsubscribe("test.topic", callback)

        # 发布第二条消息
        await bus.publish("test.topic", {"data": "message2"})
        await asyncio.sleep(0.1)

        # 应该只收到第一条消息
        assert len(received_messages) == 1


class TestMessageBusRequestResponse:
    """测试请求-响应模式"""

    @pytest.mark.asyncio
    async def test_request_response_success(self):
        """测试成功的请求-响应"""
        bus = MessageBus()
        await bus.start()

        # 模拟 Agent 响应
        async def agent_handler(message):
            request_id = message["payload"]["request_id"]
            response_topic = message["payload"]["response_topic"]

            # 发送响应
            await bus.publish(
                response_topic,
                {
                    "request_id": request_id,
                    "result": "success"
                },
                MessageType.AGENT_RESPONSE
            )

        # 订阅请求
        await bus.subscribe("request.TestAgent", agent_handler)

        # 发送请求
        response = await bus.request_response(
            "TestAgent",
            {"action": "test"},
            timeout=5
        )

        assert response is not None
        assert response["result"] == "success"

    @pytest.mark.asyncio
    async def test_request_response_timeout(self):
        """测试请求超时"""
        bus = MessageBus()
        await bus.start()

        # 不设置响应处理器，导致超时

        # 发送请求
        response = await bus.request_response(
            "NonExistentAgent",
            {"action": "test"},
            timeout=1
        )

        assert response is None


class TestMessageBusBroadcast:
    """测试广播功能"""

    @pytest.mark.asyncio
    async def test_broadcast(self):
        """测试广播消息"""
        bus = MessageBus()
        await bus.start()

        received_messages = []

        async def callback(message):
            received_messages.append(message)

        # 订阅广播
        await bus.subscribe("broadcast.all", callback)

        # 广播
        await bus.broadcast({"announcement": "test broadcast"})

        # 等待消息处理
        await asyncio.sleep(0.1)

        assert len(received_messages) == 1
        assert received_messages[0]["payload"]["announcement"] == "test broadcast"


class TestMessageBusStats:
    """测试统计功能"""

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """测试获取统计信息"""
        bus = MessageBus()
        await bus.start()

        async def callback(message):
            pass

        # 添加订阅
        await bus.subscribe("topic1", callback)
        await bus.subscribe("topic2", callback)
        await bus.subscribe("topic2", callback)

        stats = bus.get_stats()

        assert stats["running"] is True
        assert stats["total_topics"] == 2
        assert stats["total_subscribers"] == 3
        assert "topic1" in stats["topics"]
        assert "topic2" in stats["topics"]


class TestMessageBusErrorHandling:
    """测试错误处理"""

    @pytest.mark.asyncio
    async def test_callback_exception(self):
        """测试回调函数异常"""
        bus = MessageBus()
        await bus.start()

        async def failing_callback(message):
            raise Exception("Callback error")

        # 订阅
        await bus.subscribe("test.topic", failing_callback)

        # 发布（不应该抛出异常）
        await bus.publish("test.topic", {"data": "test"})

        # 等待消息处理
        await asyncio.sleep(0.1)

        # 消息总线应该继续运行
        stats = bus.get_stats()
        assert stats["running"] is True
