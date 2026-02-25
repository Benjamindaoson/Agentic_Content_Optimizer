"""
Dots LLM Provider
小红书 dots.llm1 模型集成 (MoE 142B, 激活 14B)

模型:
- dots.llm1.inst: 指令对齐版本 (推荐用于 Writer Agent)
- dots.llm1.base: 基础版本 (用于继续预训练)

架构: MoE (Mixture of Experts)
- 总参数: 142B
- 激活参数: 14B
- 上下文: 32K tokens

优势:
1. 中文原生优化 (小红书训练)
2. 开源 MIT 许可
3. 支持 vLLM / SGLang 高效推理
4. 适合 LoRA / QLoRA 微调
"""

from typing import List, Dict, Any, Optional, AsyncGenerator, Union
import httpx
import logging

from app.core.config import get_settings
from app.engine.llm.providers.base import BaseLLMProvider

settings = get_settings()
logger = logging.getLogger(__name__)


class DotsLLMProvider(BaseLLMProvider):
    """
    Dots LLM Provider (小红书 dots.llm1)

    支持的部署方式:
    1. vLLM (推荐) - 高性能推理
    2. SGLang - 结构化生成
    3. Transformers - 标准推理
    4. 本地微调模型
    """

    MODELS = {
        "inst": "rednote-hilab/dots.llm1.inst",  # 指令对齐版本
        "base": "rednote-hilab/dots.llm1.base"   # 基础版本
    }

    def __init__(
        self,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        初始化 Dots LLM Provider

        Args:
            api_base: API 地址 (vLLM/SGLang 服务地址)
            api_key: API 密钥 (可选)
        """
        # 从配置读取或使用默认值
        self.api_base = api_base or getattr(settings, 'DOTS_API_BASE', 'http://localhost:8000')
        self.api_key = api_key or getattr(settings, 'DOTS_API_KEY', None)

        self.client = httpx.AsyncClient(
            base_url=self.api_base,
            timeout=60.0
        )

        self.default_model = self.MODELS["inst"]

        logger.info(f"Dots LLM Provider initialized: {self.api_base}")

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        system: Optional[str] = None,
        stream: bool = False,
        **kwargs
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

        Returns:
            文本响应或流式生成器
        """
        model_name = self._resolve_model_name(model)

        # 添加系统提示
        if system:
            messages = [{"role": "system", "content": system}] + messages

        # 构建请求
        request_data = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }

        # 添加额外参数
        request_data.update(kwargs)

        try:
            if stream:
                return self._stream_completion(request_data)
            else:
                response = await self.client.post(
                    "/v1/chat/completions",
                    json=request_data,
                    headers=self._get_headers()
                )
                response.raise_for_status()

                result = response.json()
                return result["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"Dots LLM API error: {e}")
            raise

    async def _stream_completion(
        self,
        request_data: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """流式补全"""
        try:
            async with self.client.stream(
                "POST",
                "/v1/chat/completions",
                json=request_data,
                headers=self._get_headers()
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]  # 移除 "data: " 前缀

                        if data == "[DONE]":
                            break

                        try:
                            import json
                            chunk = json.loads(data)
                            content = chunk["choices"][0]["delta"].get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            logger.error(f"Dots LLM streaming error: {e}")
            raise

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            "Content-Type": "application/json"
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

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
        """
        结构化输出

        Args:
            messages: 对话消息
            schema: JSON Schema
            model: 模型名称
            temperature: 温度参数

        Returns:
            解析后的 JSON 对象
        """
        # 添加 JSON 格式要求
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

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            response = await self.client.get("/health")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}

    async def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        try:
            response = await self.client.get("/v1/models")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Get model info failed: {e}")
            return {"error": str(e)}


class DotsLLMLocalProvider(BaseLLMProvider):
    """
    Dots LLM Local Provider
    使用 Transformers 本地加载模型 (用于微调后的模型)
    """

    def __init__(
        self,
        model_path: str,
        device: str = "cuda",
        load_in_8bit: bool = False,
        load_in_4bit: bool = False
    ):
        """
        初始化本地 Dots LLM Provider

        Args:
            model_path: 模型路径 (本地路径或 HuggingFace 模型 ID)
            device: 设备 (cuda/cpu)
            load_in_8bit: 是否使用 8-bit 量化
            load_in_4bit: 是否使用 4-bit 量化
        """
        self.model_path = model_path
        self.device = device

        # 延迟加载 (避免启动时加载大模型)
        self.model = None
        self.tokenizer = None

        self.load_in_8bit = load_in_8bit
        self.load_in_4bit = load_in_4bit

        logger.info(f"Dots LLM Local Provider initialized: {model_path}")

    def _load_model(self):
        """加载模型 (延迟加载)"""
        if self.model is not None:
            return

        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch

            logger.info(f"Loading Dots LLM model from {self.model_path}...")

            # 加载 tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_path,
                trust_remote_code=True
            )

            # 加载模型
            load_kwargs = {
                "trust_remote_code": True,
                "torch_dtype": torch.float16 if self.device == "cuda" else torch.float32
            }

            if self.load_in_8bit:
                load_kwargs["load_in_8bit"] = True
            elif self.load_in_4bit:
                load_kwargs["load_in_4bit"] = True

            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                **load_kwargs
            )

            if not (self.load_in_8bit or self.load_in_4bit):
                self.model = self.model.to(self.device)

            self.model.eval()

            logger.info("Dots LLM model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load Dots LLM model: {e}")
            raise

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
        # 确保模型已加载
        self._load_model()

        # 构建提示词
        prompt = self._build_prompt(messages, system)

        # 编码
        inputs = self.tokenizer(prompt, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # 生成
        import torch

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=temperature > 0,
                top_p=0.9,
                repetition_penalty=1.1
            )

        # 解码
        response = self.tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True
        )

        return response

    def _build_prompt(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None
    ) -> str:
        """构建提示词"""
        # dots.llm1.inst 使用的对话格式
        prompt_parts = []

        if system:
            prompt_parts.append(f"System: {system}\n")

        for message in messages:
            role = message["role"]
            content = message["content"]

            if role == "user":
                prompt_parts.append(f"User: {content}\n")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}\n")

        prompt_parts.append("Assistant: ")

        return "".join(prompt_parts)

    async def structured_output(
        self,
        messages: List[Dict[str, str]],
        schema: Dict[str, Any],
        model: Optional[str] = None,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """结构化输出"""
        system_prompt = f"""You must respond with valid JSON matching this schema:
{schema}

Respond ONLY with the JSON object, no additional text."""

        response = await self.chat_completion(
            messages=messages,
            temperature=temperature,
            system=system_prompt
        )

        import json
        return json.loads(response)


# 全局实例 (根据配置选择)
def create_dots_provider(use_local: bool = False) -> BaseLLMProvider:
    """
    创建 Dots LLM Provider

    Args:
        use_local: 是否使用本地模型

    Returns:
        DotsLLMProvider 或 DotsLLMLocalProvider
    """
    if use_local:
        # 使用本地微调后的模型
        model_path = getattr(settings, 'DOTS_LOCAL_MODEL_PATH', './models/dots-llm-finetuned')
        return DotsLLMLocalProvider(
            model_path=model_path,
            device="cuda",
            load_in_4bit=True  # 使用 4-bit 量化节省显存
        )
    else:
        # 使用 vLLM/SGLang 服务
        return DotsLLMProvider()
