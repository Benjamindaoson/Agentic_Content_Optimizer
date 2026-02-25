"""
DeepSeek LLM Provider
DeepSeek-V3: 开源最强模型 (2025)
"""

from typing import List, Dict, Any, Optional, AsyncGenerator, Union
from openai import AsyncOpenAI
import logging

from app.core.config import get_settings
from app.engine.llm.providers.base import BaseLLMProvider

settings = get_settings()
logger = logging.getLogger(__name__)


class DeepSeekProvider(BaseLLMProvider):
    """
    DeepSeek LLM Provider

    Models:
    - deepseek-chat: DeepSeek-V3 (671B MoE, 开源最强)
    - deepseek-coder: DeepSeek-Coder-V2 (代码专用)
    """

    MODELS = {
        "v3": "deepseek-chat",
        "coder": "deepseek-coder"
    }

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY if hasattr(settings, 'DEEPSEEK_API_KEY') else None,
            base_url="https://api.deepseek.com"
        ) if hasattr(settings, 'DEEPSEEK_API_KEY') else None
        self.default_model = self.MODELS["v3"]

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        system: Optional[str] = None,
        stream: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
        """聊天补全"""
        if not self.client:
            logger.warning("DeepSeek API key not configured, using mock response")
            return "Mock DeepSeek response: " + messages[-1].get("content", "")

        model_name = self._resolve_model_name(model)

        # 添加系统提示到消息
        if system:
            messages = [{"role": "system", "content": system}] + messages

        try:
            if stream:
                return self._stream_completion(
                    messages=messages,
                    model=model_name,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            else:
                response = await self.client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                return response.choices[0].message.content

        except Exception as e:
            logger.error(f"DeepSeek API error: {e}")
            raise

    async def _stream_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int
    ) -> AsyncGenerator[str, None]:
        """流式补全"""
        try:
            stream = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"DeepSeek streaming error: {e}")
            raise

    def _resolve_model_name(self, model: Optional[str]) -> str:
        """解析模型名称"""
        if not model:
            return self.default_model

        if model in self.MODELS:
            return self.MODELS[model]

        return model

    async def structured_output(
        self,
        messages: List[Dict[str, str]],
        schema: Dict[str, Any],
        model: Optional[str] = None,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """结构化输出"""
        try:
            system_prompt = f"""You must respond with valid JSON matching this schema:
{schema}

Respond ONLY with the JSON object, no additional text."""

            response = await self.chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                system=system_prompt
            )

            import json
            return json.loads(response)

        except Exception as e:
            logger.error(f"Structured output error: {e}")
            raise
