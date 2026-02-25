from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel
import logging
import asyncio

logger = logging.getLogger(__name__)


class AgentConfig(BaseModel):
    """Agent 配置"""
    name: str
    description: str
    model: str = "claude-3-5-sonnet-20240620"
    temperature: float = 0.7
    max_tokens: int = 4000
    timeout: int = 60


class AgentResponse(BaseModel):
    """Agent 响应"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}


class BaseAgent(ABC):
    """Agent 基类"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{config.name}")

    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """执行 Agent 任务"""
        pass

    async def execute_with_timeout(self, input_data: Dict[str, Any]) -> AgentResponse:
        """带超时控制的执行方法"""
        try:
            # 使用配置中的超时时间
            async with asyncio.timeout(self.config.timeout):
                return await self.execute(input_data)
        except asyncio.TimeoutError:
            self.logger.error(f"{self.config.name} execution timeout after {self.config.timeout}s")
            return AgentResponse(
                success=False,
                error=f"Execution timeout after {self.config.timeout} seconds",
                metadata={"agent": self.config.name, "timeout": self.config.timeout}
            )
        except Exception as e:
            return await self._handle_error(e)

    async def _handle_error(self, error: Exception) -> AgentResponse:
        """统一错误处理"""
        self.logger.error(f"{self.config.name} error: {error}", exc_info=True)
        return AgentResponse(
            success=False,
            error=str(error),
            metadata={"agent": self.config.name}
        )

    def _log_execution(self, input_data: Dict[str, Any], response: AgentResponse):
        """记录执行日志"""
        self.logger.info(
            f"{self.config.name} executed",
            extra={
                "input": input_data,
                "success": response.success,
                "metadata": response.metadata
            }
        )
