"""
Unified LLM Manager
统一管理所有 LLM 提供者 (2025-2026 最新模型)
"""

from typing import List, Dict, Any, Optional, Union, AsyncGenerator
from enum import Enum
import logging

from app.engine.llm.providers.claude import ClaudeProvider
from app.engine.llm.providers.openai import OpenAIProvider
from app.engine.llm.providers.deepseek import DeepSeekProvider
from app.engine.llm.providers.gemini import GeminiProvider
from app.engine.llm.providers.dots import DotsLLMProvider

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """LLM 提供者枚举"""
    CLAUDE = "claude"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"
    DOTS = "dots"  # 小红书 dots.llm1 (推荐用于中文内容生成)


class UnifiedLLM:
    """
    统一 LLM 管理器

    支持的模型 (2025-2026):

    Anthropic Claude:
    - claude-opus-4-6: 最强模型 (200K context)
    - claude-sonnet-4-5: 平衡性能 (200K context)
    - claude-haiku-4-5: 快速响应 (200K context)

    OpenAI:
    - gpt-4.5-turbo: 最新 GPT (128K context)
    - o1: 推理模型 (128K context)
    - o1-mini: 快速推理 (128K context)

    DeepSeek (开源):
    - deepseek-v3: 开源最强 (671B MoE)
    - deepseek-coder: 代码专用

    Google Gemini:
    - gemini-2.0-flash: 快速高效 (2M context)
    - gemini-2.0-pro: 最强性能 (2M context)

    Dots LLM (小红书, 推荐):
    - dots.llm1.inst: 中文内容生成专用 (MoE 142B, 激活 14B)
    - dots.llm1.base: 基础版本 (用于继续预训练)
    """

    def __init__(self):
        self.providers = {
            LLMProvider.CLAUDE: ClaudeProvider(),
            LLMProvider.OPENAI: OpenAIProvider(),
            LLMProvider.DEEPSEEK: DeepSeekProvider(),
            LLMProvider.GEMINI: GeminiProvider(),
            LLMProvider.DOTS: DotsLLMProvider()
        }

        # 默认提供者 (推荐使用 Dots LLM 用于中文内容生成)
        self.default_provider = LLMProvider.DOTS

    async def chat(
        self,
        messages: List[Dict[str, str]],
        provider: Optional[Union[str, LLMProvider]] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        system: Optional[str] = None,
        stream: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, str]] = None,
        use_cache: bool = False
    ) -> Union[str, AsyncGenerator[str, None], Dict[str, Any]]:
        """
        统一聊天接口

        Args:
            messages: 对话消息
            provider: LLM 提供者 ("claude", "openai", "deepseek", "gemini")
            model: 模型名称 (支持简写)
            temperature: 温度参数
            max_tokens: 最大 token 数
            system: 系统提示
            stream: 是否流式输出
            tools: 工具定义 (仅 Claude 支持)
            tool_choice: 工具选择策略
            use_cache: 是否使用 Prompt Caching (仅 Claude 支持)

        Returns:
            文本响应 或 流式生成器 或 工具调用结果
        """
        # 解析提供者
        if isinstance(provider, str):
            provider = LLMProvider(provider)
        elif provider is None:
            provider = self.default_provider

        # 获取提供者实例
        provider_instance = self.providers[provider]

        # 调用对应的提供者
        if provider == LLMProvider.CLAUDE:
            return await provider_instance.chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                system=system,
                stream=stream,
                tools=tools,
                tool_choice=tool_choice,
                use_cache=use_cache
            )
        else:
            return await provider_instance.chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                system=system,
                stream=stream
            )

    async def structured_output(
        self,
        messages: List[Dict[str, str]],
        schema: Dict[str, Any],
        provider: Optional[Union[str, LLMProvider]] = None,
        model: Optional[str] = None,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        结构化输出 (JSON)

        Args:
            messages: 对话消息
            schema: JSON Schema
            provider: LLM 提供者
            model: 模型名称
            temperature: 温度参数

        Returns:
            解析后的 JSON 对象
        """
        # 解析提供者
        if isinstance(provider, str):
            provider = LLMProvider(provider)
        elif provider is None:
            provider = self.default_provider

        # 获取提供者实例
        provider_instance = self.providers[provider]

        return await provider_instance.structured_output(
            messages=messages,
            schema=schema,
            model=model,
            temperature=temperature
        )

    async def compare_models(
        self,
        messages: List[Dict[str, str]],
        providers: List[Union[str, LLMProvider]],
        system: Optional[str] = None
    ) -> Dict[str, str]:
        """
        并行比较多个模型的输出

        Args:
            messages: 对话消息
            providers: 要比较的提供者列表
            system: 系统提示

        Returns:
            {provider_name: response}
        """
        import asyncio

        tasks = []
        for provider in providers:
            task = self.chat(
                messages=messages,
                provider=provider,
                system=system
            )
            tasks.append((provider, task))

        gathered = await asyncio.gather(
            *[t for _, t in tasks], return_exceptions=True
        )

        results = {}
        for (provider, _), resp in zip(tasks, gathered):
            if isinstance(resp, Exception):
                logger.error(f"Error with provider {provider}: {resp}")
                results[str(provider)] = f"Error: {resp}"
            else:
                results[str(provider)] = resp

        return results

    def get_model_info(self, provider: Union[str, LLMProvider]) -> Dict[str, Any]:
        """获取模型信息"""
        if isinstance(provider, str):
            provider = LLMProvider(provider)

        provider_instance = self.providers[provider]

        if hasattr(provider_instance, 'MODELS'):
            return {
                "provider": provider.value,
                "models": provider_instance.MODELS,
                "default_model": provider_instance.default_model
            }

        return {"provider": provider.value}

    def list_all_models(self) -> Dict[str, Dict[str, Any]]:
        """列出所有可用模型"""
        all_models = {}
        for provider in LLMProvider:
            all_models[provider.value] = self.get_model_info(provider)
        return all_models


# 全局实例
unified_llm = UnifiedLLM()
