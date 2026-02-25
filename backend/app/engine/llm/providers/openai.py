from typing import List, Dict, Any, Optional, AsyncGenerator, Union
from openai import AsyncOpenAI
import logging

from app.core.config import get_settings
from app.engine.llm.providers.base import BaseLLMProvider

settings = get_settings()
logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI LLM Provider (2025-2026 Latest Models)

    Supported Models:
    - gpt-4o: Most capable model
    - gpt-4-turbo: Fast and capable
    - gpt-3.5-turbo: Cost-effective
    """

    # Latest model definitions (2025-2026)
    MODELS = {
        "gpt-4o": "gpt-4o",
        "gpt-4-turbo": "gpt-4-turbo",
        "gpt-3.5-turbo": "gpt-3.5-turbo"
    }

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY else None
        self.default_model = self.MODELS["gpt-4o"]

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
        聊天补全

        Args:
            messages: 对话消息
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大 token 数
            system: 系统提示
            stream: 是否流式输出
            tools: 工具定义
            tool_choice: 工具选择策略
            use_cache: 是否使用缓存 (OpenAI 不支持)

        Returns:
            完成的文本或流式生成器
        """
        if not self.client:
            raise ValueError("OpenAI API key not configured")

        model = model or self.default_model

        # 构建消息
        formatted_messages = []
        if system:
            formatted_messages.append({"role": "system", "content": system})
        formatted_messages.extend(messages)

        try:
            if stream:
                return self._stream_completion(formatted_messages, model, temperature, max_tokens, tools, tool_choice)
            else:
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=formatted_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    tool_choice=tool_choice
                )
                return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    async def _stream_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        tools: Optional[List[Dict[str, Any]]],
        tool_choice: Optional[Dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        """流式补全"""
        stream = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            stream=True
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def embedding(
        self,
        texts: Union[str, List[str]],
        model: str = "text-embedding-3-large"
    ) -> List[List[float]]:
        """
        生成文本嵌入

        Args:
            texts: 单个文本或文本列表
            model: 嵌入模型

        Returns:
            嵌入向量列表
        """
        if not self.client:
            raise ValueError("OpenAI API key not configured")

        if isinstance(texts, str):
            texts = [texts]

        try:
            response = await self.client.embeddings.create(
                model=model,
                input=texts
            )
            return [item.embedding for item in response.data]

        except Exception as e:
            logger.error(f"OpenAI embedding error: {e}")
            raise

    async def structured_output(
        self,
        messages: List[Dict[str, str]],
        schema: Dict[str, Any],
        model: Optional[str] = None,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        结构化输出

        Args:
            messages: 对话消息
            schema: JSON Schema
            model: 模型名称
            temperature: 温度参数

        Returns:
            结构化输出结果
        """
        if not self.client:
            raise ValueError("OpenAI API key not configured")

        model = model or self.default_model

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
                tools=[{
                    "type": "function",
                    "function": {
                        "name": "output",
                        "description": "Output structured data",
                        "parameters": schema
                    }
                }],
                tool_choice={"type": "function", "function": {"name": "output"}}
            )

            # Extract structured output from tool call
            if response.choices[0].message.tool_calls:
                import json
                return json.loads(response.choices[0].message.tool_calls[0].function.arguments)
            else:
                # Fallback to parsing JSON from content
                import json
                return json.loads(response.choices[0].message.content)

        except Exception as e:
            logger.error(f"OpenAI structured output error: {e}")
            raise
