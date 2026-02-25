"""
Adapter Loader

动态加载和管理 adapters
"""

import torch
from typing import Optional, Dict, Any
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import logging

from .adapter_registry import AdapterRegistry, AdapterRecord

logger = logging.getLogger(__name__)


class AdapterLoader:
    """Adapter 加载器"""

    def __init__(self, registry: AdapterRegistry):
        self.registry = registry
        self._loaded_models: Dict[str, tuple] = {}  # adapter_name -> (model, tokenizer)

    def load(
        self,
        adapter_name: Optional[str] = None,
        platform: Optional[str] = None,
        persona: Optional[str] = None,
        niche: Optional[str] = None,
        device_map: str = "auto",
    ) -> tuple:
        """加载 adapter

        Returns:
            (model, tokenizer, adapter_record)
        """
        # 获取 adapter 记录
        if adapter_name:
            adapter = self.registry.get(adapter_name)
            if not adapter:
                raise ValueError(f"Adapter {adapter_name} 不存在")
        else:
            # 使用默认 adapter
            adapter = self.registry.get_default(platform=platform, persona=persona, niche=niche)
            if not adapter:
                raise ValueError(f"未找到默认 adapter (platform={platform}, persona={persona}, niche={niche})")

        logger.info(f"加载 adapter: {adapter.adapter_name}")

        # 检查缓存
        if adapter.adapter_name in self._loaded_models:
            logger.info(f"从缓存加载 adapter: {adapter.adapter_name}")
            model, tokenizer = self._loaded_models[adapter.adapter_name]
            return model, tokenizer, adapter

        # 加载基础模型
        logger.info(f"加载基础模型: {adapter.base_model}")
        base_model = AutoModelForCausalLM.from_pretrained(
            adapter.base_model,
            device_map=device_map,
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
        )

        # 加载 adapter
        logger.info(f"加载 adapter 权重: {adapter.adapter_path}")
        model = PeftModel.from_pretrained(base_model, adapter.adapter_path)

        # 加载 tokenizer
        tokenizer = AutoTokenizer.from_pretrained(
            adapter.adapter_path,
            trust_remote_code=True,
        )
        tokenizer.pad_token = tokenizer.eos_token

        # 缓存
        self._loaded_models[adapter.adapter_name] = (model, tokenizer)

        logger.info(f"Adapter {adapter.adapter_name} 加载完成")
        return model, tokenizer, adapter

    def unload(self, adapter_name: str):
        """卸载 adapter"""
        if adapter_name in self._loaded_models:
            del self._loaded_models[adapter_name]
            torch.cuda.empty_cache()
            logger.info(f"Adapter {adapter_name} 已卸载")

    def clear_cache(self):
        """清空缓存"""
        self._loaded_models.clear()
        torch.cuda.empty_cache()
        logger.info("Adapter 缓存已清空")

    def generate(
        self,
        prompt: str,
        adapter_name: Optional[str] = None,
        platform: Optional[str] = None,
        persona: Optional[str] = None,
        niche: Optional[str] = None,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 50,
    ) -> Dict[str, Any]:
        """使用 adapter 生成文本"""
        # 加载 adapter
        model, tokenizer, adapter = self.load(
            adapter_name=adapter_name,
            platform=platform,
            persona=persona,
            niche=niche,
        )

        # 生成
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=True,
                top_p=top_p,
                top_k=top_k,
                pad_token_id=tokenizer.eos_token_id,
            )

        generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)

        # 移除输入部分
        generated_text = generated_text[len(prompt):].strip()

        return {
            "text": generated_text,
            "adapter_name": adapter.adapter_name,
            "adapter_type": adapter.adapter_type,
            "platform": adapter.platform,
            "persona": adapter.persona,
            "niche": adapter.niche,
        }
