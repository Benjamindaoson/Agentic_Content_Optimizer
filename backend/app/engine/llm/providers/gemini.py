"""
Gemini LLM Provider
Google Gemini 2.0 (2025)
"""

from typing import List, Dict, Any, Optional, AsyncGenerator, Union
import google.generativeai as genai
import logging

from app.core.config import get_settings
from app.engine.llm.providers.base import BaseLLMProvider

settings = get_settings()
logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """
    Gemini LLM Provider

    Models:
    - gemini-2.0-flash: Fast and efficient (2M context)
    - gemini-2.0-pro: Most capable (2M context)
    - gemini-1.5-pro: Previous generation (2M context)
    """

    MODELS = {
        "2.0-flash": "gemini-2.0-flash-exp",
        "2.0-pro": "gemini-2.0-pro-exp",
        "1.5-pro": "gemini-1.5-pro-latest"
    }

    def __init__(self):
        if hasattr(settings, 'GOOGLE_API_KEY') and settings.GOOGLE_API_KEY:
            genai.configure(api_key=settings.GOOGLE_API_KEY)
            self.client = genai
        else:
            self.client = None

        self.default_model = self.MODELS["2.0-flash"]

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
            logger.warning("Gemini API key not configured, using mock response")
            return "Mock Gemini response: " + messages[-1].get("content", "")

        model_name = self._resolve_model_name(model)

        try:
            # 创建模型实例
            model_instance = self.client.GenerativeModel(
                model_name=model_name,
                system_instruction=system
            )

            # 转换消息格式
            gemini_messages = self._convert_messages(messages)

            # 生成配置
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens
            }

            if stream:
                return self._stream_completion(
                    model_instance=model_instance,
                    messages=gemini_messages,
                    generation_config=generation_config
                )
            else:
                response = await model_instance.generate_content_async(
                    gemini_messages,
                    generation_config=generation_config
                )
                return response.text

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise

    async def _stream_completion(
        self,
        model_instance,
        messages: List[str],
        generation_config: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """流式补全"""
        try:
            response = await model_instance.generate_content_async(
                messages,
                generation_config=generation_config,
                stream=True
            )

            async for chunk in response:
                if chunk.text:
                    yield chunk.text

        except Exception as e:
            logger.error(f"Gemini streaming error: {e}")
            raise

    def _convert_messages(self, messages: List[Dict[str, str]]) -> List[str]:
        """转换消息格式为 Gemini 格式"""
        # Gemini 使用简单的字符串列表
        # 或者 {"role": "user/model", "parts": ["text"]}
        converted = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else "user"
            converted.append({
                "role": role,
                "parts": [msg["content"]]
            })
        return converted

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
