from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from app.engine.llm.providers.base import BaseLLMProvider
from app.engine.llm.unified import unified_llm


class UnifiedLLMProviderAdapter(BaseLLMProvider):
    """
    将 UnifiedLLM 适配为 BaseLLMProvider，便于在 Agent 中作为 llm_provider 注入。

    说明：
    - provider/model/temperature/max_tokens 会作为默认值
    - 调用方若传入覆盖参数，以传入为准
    """

    def __init__(
        self,
        provider: str,
        model: Optional[str],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        system: Optional[str] = None,
    ):
        self._provider = provider
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._system = system

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        system: Optional[str] = None,
        stream: bool = False,
    ) -> Union[str, AsyncGenerator[str, None]]:
        return await unified_llm.chat(
            messages=messages,
            provider=self._provider,
            model=model or self._model,
            temperature=temperature if temperature is not None else self._temperature,
            max_tokens=max_tokens or self._max_tokens,
            system=system or self._system,
            stream=stream,
        )

    async def structured_output(
        self,
        messages: List[Dict[str, str]],
        schema: Dict[str, Any],
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        return await unified_llm.structured_output(
            messages=messages,
            schema=schema,
            provider=self._provider,
            model=model or self._model,
            temperature=temperature if temperature is not None else self._temperature,
        )

