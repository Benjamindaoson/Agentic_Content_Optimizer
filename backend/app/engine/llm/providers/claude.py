from typing import List, Dict, Any, Optional, AsyncGenerator, Union
from anthropic import AsyncAnthropic
import logging

from app.core.config import get_settings
from app.engine.llm.providers.base import BaseLLMProvider

settings = get_settings()
logger = logging.getLogger(__name__)


class ClaudeProvider(BaseLLMProvider):
    """
    Claude LLM Provider (2025-2026 Latest Models)

    Supported Models:
    - claude-opus-4-6: Most capable model (200K context)
    - claude-sonnet-4-5: Balanced performance (200K context)
    - claude-3-5-sonnet: Previous generation (200K context)
    """

    # Latest model definitions (2025-2026)
    MODELS = {
        "opus-4.6": "claude-opus-4-6",
        "sonnet-4.5": "claude-sonnet-4-5-20250929",
        "sonnet-3.5": "claude-3-5-sonnet-20241022",
        "haiku-4.5": "claude-haiku-4-5-20251001"
    }

    def __init__(self):
        self.client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY) if settings.ANTHROPIC_API_KEY else None
        self.default_model = self.MODELS["sonnet-4.5"]  # Use latest Sonnet 4.5

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        system: Optional[str] = None,
        stream: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, str]] = None,
        use_cache: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
        """
        聊天补全 (支持 Tool Use + Prompt Caching)

        Args:
            messages: 对话消息
            model: 模型名称 (支持简写: "opus-4.6", "sonnet-4.5")
            temperature: 温度参数
            max_tokens: 最大 token 数
            system: 系统提示
            stream: 是否流式输出
            tools: 工具定义 (Function Calling)
            tool_choice: 工具选择策略
            use_cache: 是否使用 Prompt Caching (减少成本 90%)
        """
        if not self.client:
            logger.warning("Claude API key not configured, using mock response")
            return "Mock Claude response: " + messages[-1].get("content", "")

        # 解析模型名称
        model_name = self._resolve_model_name(model)

        try:
            # 构建请求参数
            request_params = {
                "model": model_name,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages
            }

            # 添加系统提示 (支持 Prompt Caching)
            if system:
                if use_cache:
                    request_params["system"] = [
                        {
                            "type": "text",
                            "text": system,
                            "cache_control": {"type": "ephemeral"}  # 缓存系统提示
                        }
                    ]
                else:
                    request_params["system"] = system

            # 添加工具定义 (Function Calling)
            if tools:
                request_params["tools"] = tools
                if tool_choice:
                    request_params["tool_choice"] = tool_choice

            if stream:
                return self._stream_completion(**request_params)
            else:
                response = await self.client.messages.create(**request_params)

                # 处理工具调用
                if tools and response.stop_reason == "tool_use":
                    return {
                        "type": "tool_use",
                        "content": response.content,
                        "tool_calls": [
                            block for block in response.content
                            if block.type == "tool_use"
                        ]
                    }

                return response.content[0].text

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise

    def _resolve_model_name(self, model: Optional[str]) -> str:
        """解析模型名称 (支持简写)"""
        if not model:
            return self.default_model

        # 如果是简写，转换为完整名称
        if model in self.MODELS:
            return self.MODELS[model]

        # 否则直接使用
        return model

    async def _stream_completion(
        self,
        model: str,
        max_tokens: int,
        temperature: float,
        messages: List[Dict[str, str]],
        system: Optional[Any] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, str]] = None
    ) -> AsyncGenerator[str, None]:
        """流式补全 (支持 Tool Use)"""
        try:
            request_params = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages
            }

            if system:
                request_params["system"] = system

            if tools:
                request_params["tools"] = tools
                if tool_choice:
                    request_params["tool_choice"] = tool_choice

            async with self.client.messages.stream(**request_params) as stream:
                async for text in stream.text_stream:
                    yield text

        except Exception as e:
            logger.error(f"Claude streaming error: {e}")
            raise

    async def structured_output(
        self,
        messages: List[Dict[str, str]],
        schema: Dict[str, Any],
        model: Optional[str] = None,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """结构化输出（使用 JSON mode）"""
        try:
            # 添加 JSON 格式要求到系统提示
            system_prompt = f"""You must respond with valid JSON matching this schema:
{schema}

Respond ONLY with the JSON object, no additional text."""

            response = await self.chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                system=system_prompt
            )

            # 解析 JSON
            import json
            return json.loads(response)

        except Exception as e:
            logger.error(f"Structured output error: {e}")
            raise
