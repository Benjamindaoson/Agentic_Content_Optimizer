"""
Evaluator

评估训练的 adapters
"""

from typing import Dict, List, Any, Optional
from datasets import Dataset
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import logging
from tqdm import tqdm

from .metrics import MetricsCalculator
from ..models.adapter_registry import AdapterRegistry

logger = logging.getLogger(__name__)


class Evaluator:
    """Adapter 评估器"""

    def __init__(self, registry: AdapterRegistry):
        self.registry = registry
        self.metrics_calculator = MetricsCalculator()

    def evaluate_adapter(
        self,
        adapter_name: str,
        eval_dataset: Dataset,
        platform: Optional[str] = None,
        max_samples: Optional[int] = None,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """评估 adapter"""
        logger.info(f"评估 adapter: {adapter_name}")

        # 获取 adapter 记录
        adapter = self.registry.get(adapter_name)
        if not adapter:
            raise ValueError(f"Adapter {adapter_name} 不存在")

        # 加载模型
        logger.info(f"加载模型: {adapter.base_model}")
        base_model = AutoModelForCausalLM.from_pretrained(
            adapter.base_model,
            device_map="auto",
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
        )

        model = PeftModel.from_pretrained(base_model, adapter.adapter_path)
        model.eval()

        tokenizer = AutoTokenizer.from_pretrained(
            adapter.adapter_path,
            trust_remote_code=True,
        )
        tokenizer.pad_token = tokenizer.eos_token

        # 准备评估数据
        if max_samples:
            eval_dataset = eval_dataset.select(range(min(max_samples, len(eval_dataset))))

        logger.info(f"评估样本数: {len(eval_dataset)}")

        # 生成文本
        generated_texts = []
        reference_texts = []

        for example in tqdm(eval_dataset, desc="生成文本"):
            # 构建 prompt
            if "messages" in example:
                # SFT 格式
                messages = example["messages"]
                prompt = ""
                for msg in messages:
                    if msg["role"] == "user":
                        prompt += f"<|im_start|>user\n{msg['content']}<|im_end|>\n"
                    elif msg["role"] == "system":
                        prompt += f"<|im_start|>system\n{msg['content']}<|im_end|>\n"
                prompt += "<|im_start|>assistant\n"

                # 参考答案
                reference = next((msg["content"] for msg in messages if msg["role"] == "assistant"), "")

            elif "prompt" in example:
                # DPO 格式
                prompt = example["prompt"]
                reference = example.get("chosen", "")

            else:
                logger.warning(f"未知的数据格式: {example.keys()}")
                continue

            # 生成
            inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    do_sample=True,
                    top_p=0.9,
                    top_k=50,
                    pad_token_id=tokenizer.eos_token_id,
                )

            generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
            generated_text = generated_text[len(prompt):].strip()

            generated_texts.append(generated_text)
            reference_texts.append(reference)

        # 计算指标
        logger.info("计算评估指标...")

        metrics = self.metrics_calculator.calculate_all_metrics(
            generated_texts=generated_texts,
            reference_texts=reference_texts if reference_texts else None,
            platform=platform or adapter.platform,
        )

        # 添加样本数
        metrics["num_samples"] = len(generated_texts)

        # 保存示例
        metrics["examples"] = [
            {
                "reference": ref,
                "generated": gen,
            }
            for ref, gen in zip(reference_texts[:5], generated_texts[:5])
        ]

        logger.info(f"评估完成: {metrics}")

        # 更新 adapter 记录
        self.registry.update_metrics(adapter_name, metrics)

        return metrics

    def compare_adapters(
        self,
        adapter_names: List[str],
        eval_dataset: Dataset,
        platform: Optional[str] = None,
        max_samples: Optional[int] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """对比多个 adapters"""
        logger.info(f"对比 adapters: {adapter_names}")

        results = {}

        for adapter_name in adapter_names:
            try:
                metrics = self.evaluate_adapter(
                    adapter_name=adapter_name,
                    eval_dataset=eval_dataset,
                    platform=platform,
                    max_samples=max_samples,
                )
                results[adapter_name] = metrics

            except Exception as e:
                logger.error(f"评估 {adapter_name} 失败: {e}")
                results[adapter_name] = {"error": str(e)}

        # 生成对比报告
        comparison = self._generate_comparison_report(results)

        return {
            "individual_results": results,
            "comparison": comparison,
        }

    def _generate_comparison_report(self, results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """生成对比报告"""
        report = {}

        # 提取所有指标
        all_metrics = set()
        for metrics in results.values():
            if "error" not in metrics:
                all_metrics.update(metrics.keys())

        # 移除非数值指标
        numeric_metrics = [m for m in all_metrics if m not in ["examples", "length", "num_samples"]]

        # 对比每个指标
        for metric in numeric_metrics:
            values = {}
            for adapter_name, metrics in results.items():
                if "error" not in metrics and metric in metrics:
                    values[adapter_name] = metrics[metric]

            if values:
                best_adapter = max(values, key=values.get)
                report[metric] = {
                    "values": values,
                    "best": best_adapter,
                    "best_value": values[best_adapter],
                }

        return report

    def evaluate_on_real_data(
        self,
        adapter_name: str,
        platform: str,
        days: int = 7,
        min_samples: int = 100,
    ) -> Dict[str, Any]:
        """在真实数据上评估"""
        from datetime import datetime, timedelta
        from sqlalchemy.orm import Session
        from ..training.schemas import GenerationTrace, Outcome

        logger.info(f"在真实数据上评估 adapter: {adapter_name}")

        # 获取 adapter
        adapter = self.registry.get(adapter_name)
        if not adapter:
            raise ValueError(f"Adapter {adapter_name} 不存在")

        # 查询真实数据
        from app.core.database import SessionLocal
        db = SessionLocal()

        start_date = datetime.utcnow() - timedelta(days=days)

        traces = db.query(GenerationTrace).join(Outcome).filter(
            GenerationTrace.platform == platform,
            GenerationTrace.adapter_id == adapter_name,
            GenerationTrace.created_at >= start_date,
        ).all()

        db.close()

        if len(traces) < min_samples:
            logger.warning(f"样本数不足: {len(traces)} < {min_samples}")
            return {
                "error": f"样本数不足: {len(traces)} < {min_samples}",
                "num_samples": len(traces),
            }

        # 计算真实指标
        engagement_scores = []
        click_rates = []
        completion_rates = []

        for trace in traces:
            if trace.outcomes:
                outcome = trace.outcomes[0]
                engagement_scores.append(outcome.engagement_score)
                click_rates.append(outcome.click_rate)
                completion_rates.append(outcome.completion_rate)

        import numpy as np

        metrics = {
            "num_samples": len(traces),
            "engagement_score": {
                "mean": np.mean(engagement_scores),
                "std": np.std(engagement_scores),
                "median": np.median(engagement_scores),
            },
            "click_rate": {
                "mean": np.mean(click_rates),
                "std": np.std(click_rates),
            },
            "completion_rate": {
                "mean": np.mean(completion_rates),
                "std": np.std(completion_rates),
            },
        }

        logger.info(f"真实数据评估完成: {metrics}")

        # 更新 adapter 记录
        existing_metrics = adapter.eval_metrics or {}
        self.registry.update_metrics(adapter_name, {
            **existing_metrics,
            "real_data_metrics": metrics,
        })

        return metrics
