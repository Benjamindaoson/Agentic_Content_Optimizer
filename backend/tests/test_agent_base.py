"""
Agent 基类单元测试
Agent Base Class Unit Tests
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from app.agents.base import BaseAgent, AgentConfig, AgentResponse


@pytest.mark.unit
@pytest.mark.agent
class TestBaseAgent:
    """Agent 基类测试"""

    @pytest.fixture
    def agent_config(self):
        """Agent 配置"""
        return AgentConfig(
            name="TestAgent",
            description="测试 Agent",
            timeout=30,
            max_retries=3
        )

    @pytest.fixture
    def test_agent(self, agent_config):
        """测试 Agent 实例"""
        class TestAgent(BaseAgent):
            async def execute(self, input_data):
                return AgentResponse(
                    success=True,
                    data={"result": "test"}
                )

        return TestAgent(config=agent_config)

    def test_initialization(self, test_agent, agent_config):
        """测试初始化"""
        assert test_agent.config == agent_config
        assert test_agent.config.name == "TestAgent"

    @pytest.mark.asyncio
    async def test_execute(self, test_agent):
        """测试执行"""
        response = await test_agent.execute({"input": "test"})

        assert response.success is True
        assert "result" in response.data

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, agent_config):
        """测试超时控制"""
        class SlowAgent(BaseAgent):
            async def execute(self, input_data):
                await asyncio.sleep(5)
                return AgentResponse(success=True)

        agent = SlowAgent(config=AgentConfig(name="SlowAgent", timeout=1))

        response = await agent.execute_with_timeout({"input": "test"})

        # 验证超时
        assert response.success is False
        assert "timeout" in response.error.lower()

    @pytest.mark.asyncio
    async def test_retry_logic(self, agent_config):
        """测试重试逻辑"""
        call_count = 0

        class FailingAgent(BaseAgent):
            async def execute(self, input_data):
                nonlocal call_count
                call_count += 1

                if call_count < 3:
                    raise Exception("Temporary failure")

                return AgentResponse(success=True, data={"attempts": call_count})

        agent = FailingAgent(config=AgentConfig(name="FailingAgent", max_retries=3))

        response = await agent.execute_with_retry({"input": "test"})

        # 验证重试
        assert response.success is True
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, agent_config):
        """测试超过最大重试次数"""
        class AlwaysFailingAgent(BaseAgent):
            async def execute(self, input_data):
                raise Exception("Permanent failure")

        agent = AlwaysFailingAgent(config=AgentConfig(name="AlwaysFailingAgent", max_retries=2))

        response = await agent.execute_with_retry({"input": "test"})

        # 验证失败
        assert response.success is False
        assert "failure" in response.error.lower()

    @pytest.mark.asyncio
    async def test_agent_response_structure(self, test_agent):
        """测试响应结构"""
        response = await test_agent.execute({"input": "test"})

        # 验证响应结构
        assert hasattr(response, "success")
        assert hasattr(response, "data")
        assert hasattr(response, "error")
        assert hasattr(response, "metadata")

    def test_agent_config_validation(self):
        """测试配置验证"""
        # 有效配置
        valid_config = AgentConfig(name="ValidAgent", timeout=30)
        assert valid_config.timeout == 30

        # 无效超时
        with pytest.raises(ValueError):
            AgentConfig(name="InvalidAgent", timeout=-1)

    @pytest.mark.asyncio
    async def test_agent_metadata(self, test_agent):
        """测试元数据"""
        response = await test_agent.execute({"input": "test"})

        # 验证元数据
        assert response.metadata is not None
        assert "agent_name" in response.metadata
        assert response.metadata["agent_name"] == "TestAgent"


@pytest.mark.unit
@pytest.mark.agent
class TestAgentResponse:
    """Agent 响应测试"""

    def test_success_response(self):
        """测试成功响应"""
        response = AgentResponse(
            success=True,
            data={"result": "success"}
        )

        assert response.success is True
        assert response.data["result"] == "success"
        assert response.error is None

    def test_failure_response(self):
        """测试失败响应"""
        response = AgentResponse(
            success=False,
            error="Something went wrong"
        )

        assert response.success is False
        assert response.error == "Something went wrong"
        assert response.data is None

    def test_response_with_metadata(self):
        """测试带元数据的响应"""
        metadata = {"execution_time": 1.5, "tokens_used": 100}

        response = AgentResponse(
            success=True,
            data={"result": "success"},
            metadata=metadata
        )

        assert response.metadata == metadata
        assert response.metadata["execution_time"] == 1.5
