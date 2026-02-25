from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator, Union


class BaseLLMProvider(ABC):
    """LLM Provider 基类"""

    @abstractmethod
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
        pass

    @abstractmethod
    async def structured_output(
        self,
        messages: List[Dict[str, str]],
        schema: Dict[str, Any],
        model: Optional[str] = None,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """结构化输出"""
        pass
