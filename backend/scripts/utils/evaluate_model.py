"""
模型评估系统
评估生成模型的爆款预测能力和内容质量
"""

import os
import torch
import polars as pl
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass
import logging
from transformers import AutoTokenizer, AutoModelForCausalLM
from sklearn.metrics import ndcg_score, precision_score, recall_score
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class EvaluationMetrics:
    """评估指标"""
    # 排序指标
    ndcg_at_10: float
    ndcg_at_50: float

    # 分类指标（爆款 vs 普通）
    precision: float
    recall: float
    f1_score: float

    # 内容质量指标
    avg_hook_score: float
    avg_structure_score: float
    avg_emotion_score: float

    # 多样性指标
    unique_ratio: float
    vocab_diversity: float


class ModelEvaluator:
    """模型评估器"""

    def __init__(
        self,
        model_path: str,
        test_data_path: str,
        device: str = "cuda" if torch.cuda.is_available() else "cpu"
    ):
        self.model_path = Path(model_path)
        self.test_data_path = Path(test_data_path)
        self.device = device

        # 加载模型和 tokenizer
        logger.info(f"Loading model from {model_path}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
            device_map="auto"
        )
        self.model.eval()

        # 加载测试数据
        logger.info(f"Loading test data from {test_data_path}")
        self.test_data = pl.read_parquet(test_data_path)

    def generate_content(self, prompt: str, max_length: int = 512) -> str:
        """生成内容"""
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_length=max_length,
                num_return_sequences=1,
                temperature=0.7,
                top_p=0.9,
                do_sample=True
            )

        generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # 提取生成的部分（去掉 prompt）
        generated_content = generated_text[len(prompt):].strip()

        return generated_content

    def evaluate_ranking(self, n_samples: int = 1000) -> Dict[str, float]:
        """
        评估排序能力 - 模型能否预测哪些内容会爆款
        使用 NDCG 指标
        """
        logger.info("Evaluating ranking performance...")

        # 采样测试数据
        test_sample = self.test_data.sample(n=min(n_samples, len(self.test_data)), seed=42)

        # 真实的互动分数（作为 ground truth）
        true_scores = []
        predicted_scores = []

        for row in test_sample.iter_rows(named=True):
            # 构建 prompt
            prompt = self._build_prompt(row)

            # 生成内容
            generated = self.generate_content(prompt)

            # 计算预测分数（基于生成质量的启发式）
            pred_score = self._estimate_viral_score(generated)
            predicted_scores.append(pred_score)

            # 真实分数
            true_score = row.get("digg_count", 0) + row.get("comment_count", 0) * 2 + row.get("share_count", 0) * 3
            true_scores.append(true_score)

        # 计算 NDCG
        true_scores_array = np.array(true_scores).reshape(1, -1)
        predicted_scores_array = np.array(predicted_scores).reshape(1, -1)

        ndcg_10 = ndcg_score(true_scores_array, predicted_scores_array, k=10)
        ndcg_50 = ndcg_score(true_scores_array, predicted_scores_array, k=50)

        return {
            "ndcg_at_10": ndcg_10,
            "ndcg_at_50": ndcg_50
        }

    def evaluate_classification(self, n_samples: int = 1000, threshold_percentile: float = 0.8) -> Dict[str, float]:
        """
        评估分类能力 - 模型能否区分爆款和普通内容
        """
        logger.info("Evaluating classification performance...")

        test_sample = self.test_data.sample(n=min(n_samples, len(self.test_data)), seed=42)

        # 定义爆款阈值（top 20%）
        viral_threshold = test_sample["digg_count"].quantile(threshold_percentile)

        y_true = []
        y_pred = []

        for row in test_sample.iter_rows(named=True):
            # 真实标签
            is_viral = row["digg_count"] >= viral_threshold
            y_true.append(1 if is_viral else 0)

            # 生成并预测
            prompt = self._build_prompt(row)
            generated = self.generate_content(prompt)
            pred_score = self._estimate_viral_score(generated)

            # 预测标签（使用中位数作为阈值）
            y_pred.append(1 if pred_score > 0.5 else 0)

        # 计算指标
        precision = precision_score(y_true, y_pred, zero_division=0)
        recall = recall_score(y_true, y_pred, zero_division=0)
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        return {
            "precision": precision,
            "recall": recall,
            "f1_score": f1
        }

    def evaluate_content_quality(self, n_samples: int = 100) -> Dict[str, float]:
        """
        评估内容质量 - 结构、钩子、情绪
        """
        logger.info("Evaluating content quality...")

        test_sample = self.test_data.sample(n=min(n_samples, len(self.test_data)), seed=42)

        hook_scores = []
        structure_scores = []
        emotion_scores = []

        for row in test_sample.iter_rows(named=True):
            prompt = self._build_prompt(row)
            generated = self.generate_content(prompt)

            # 评估各维度
            hook_scores.append(self._evaluate_hook(generated))
            structure_scores.append(self._evaluate_structure(generated))
            emotion_scores.append(self._evaluate_emotion(generated))

        return {
            "avg_hook_score": np.mean(hook_scores),
            "avg_structure_score": np.mean(structure_scores),
            "avg_emotion_score": np.mean(emotion_scores)
        }

    def evaluate_diversity(self, n_samples: int = 100) -> Dict[str, float]:
        """
        评估生成多样性
        """
        logger.info("Evaluating diversity...")

        test_sample = self.test_data.sample(n=min(n_samples, len(self.test_data)), seed=42)

        generated_texts = []
        all_words = []

        for row in test_sample.iter_rows(named=True):
            prompt = self._build_prompt(row)
            generated = self.generate_content(prompt)
            generated_texts.append(generated)
            all_words.extend(generated.split())

        # 计算唯一性
        unique_ratio = len(set(generated_texts)) / len(generated_texts)

        # 计算词汇多样性
        vocab_diversity = len(set(all_words)) / len(all_words) if all_words else 0

        return {
            "unique_ratio": unique_ratio,
            "vocab_diversity": vocab_diversity
        }

    def run_full_evaluation(self) -> EvaluationMetrics:
        """运行完整评估"""
        logger.info("=" * 60)
        logger.info("Starting Full Model Evaluation")
        logger.info("=" * 60)

        # 1. 排序评估
        ranking_metrics = self.evaluate_ranking()

        # 2. 分类评估
        classification_metrics = self.evaluate_classification()

        # 3. 内容质量评估
        quality_metrics = self.evaluate_content_quality()

        # 4. 多样性评估
        diversity_metrics = self.evaluate_diversity()

        # 组合所有指标
        metrics = EvaluationMetrics(
            ndcg_at_10=ranking_metrics["ndcg_at_10"],
            ndcg_at_50=ranking_metrics["ndcg_at_50"],
            precision=classification_metrics["precision"],
            recall=classification_metrics["recall"],
            f1_score=classification_metrics["f1_score"],
            avg_hook_score=quality_metrics["avg_hook_score"],
            avg_structure_score=quality_metrics["avg_structure_score"],
            avg_emotion_score=quality_metrics["avg_emotion_score"],
            unique_ratio=diversity_metrics["unique_ratio"],
            vocab_diversity=diversity_metrics["vocab_diversity"]
        )

        # 打印结果
        self._print_metrics(metrics)

        return metrics

    def _build_prompt(self, row: Dict) -> str:
        """构建 prompt"""
        hashtags = row.get("hashtags", "")
        if isinstance(hashtags, list):
            hashtags = ", ".join(hashtags)

        prompt = f"""请根据以下信息生成一条短视频文案：

话题标签: {hashtags}
目标: 获得高互动率

请生成结构化文案（Hook + Body + CTA）：
"""
        return prompt

    def _estimate_viral_score(self, text: str) -> float:
        """
        估计爆款分数（启发式）
        基于文本特征
        """
        score = 0.0

        # 长度合适（50-200字）
        length = len(text)
        if 50 <= length <= 200:
            score += 0.2

        # 包含问号（互动性）
        if "?" in text or "？" in text:
            score += 0.2

        # 包含感叹号（情绪）
        if "!" in text or "！" in text:
            score += 0.15

        # 包含数字（具体性）
        if any(char.isdigit() for char in text):
            score += 0.15

        # 包含 emoji（视觉吸引）
        # 简化判断
        score += 0.1

        # 句子数量（结构）
        sentences = text.count("。") + text.count("！") + text.count("？")
        if 3 <= sentences <= 6:
            score += 0.2

        return min(score, 1.0)

    def _evaluate_hook(self, text: str) -> float:
        """评估钩子质量"""
        # 前20个字是否有吸引力
        first_20 = text[:20]

        score = 0.0

        # 包含疑问
        if "?" in first_20 or "？" in first_20:
            score += 0.4

        # 包含数字
        if any(char.isdigit() for char in first_20):
            score += 0.3

        # 包含强情绪词
        emotion_words = ["震惊", "必看", "绝了", "太", "超", "爆"]
        if any(word in first_20 for word in emotion_words):
            score += 0.3

        return min(score, 1.0)

    def _evaluate_structure(self, text: str) -> float:
        """评估结构质量"""
        score = 0.0

        # 有明确分段
        paragraphs = text.split("\n")
        if 2 <= len(paragraphs) <= 5:
            score += 0.4

        # 有 CTA
        cta_words = ["点赞", "关注", "评论", "转发", "收藏"]
        if any(word in text for word in cta_words):
            score += 0.3

        # 长度适中
        if 80 <= len(text) <= 300:
            score += 0.3

        return min(score, 1.0)

    def _evaluate_emotion(self, text: str) -> float:
        """评估情绪强度"""
        score = 0.0

        # 感叹号数量
        exclamation_count = text.count("！") + text.count("!")
        score += min(exclamation_count * 0.1, 0.3)

        # 情绪词
        emotion_words = ["爱", "喜欢", "讨厌", "惊", "哭", "笑", "怒", "怕"]
        emotion_count = sum(1 for word in emotion_words if word in text)
        score += min(emotion_count * 0.1, 0.4)

        # 强调词
        emphasis_words = ["太", "超", "非常", "特别", "真的", "简直"]
        emphasis_count = sum(1 for word in emphasis_words if word in text)
        score += min(emphasis_count * 0.1, 0.3)

        return min(score, 1.0)

    def _print_metrics(self, metrics: EvaluationMetrics):
        """打印评估结果"""
        logger.info("\n" + "=" * 60)
        logger.info("Evaluation Results")
        logger.info("=" * 60)

        logger.info("\n📊 Ranking Metrics:")
        logger.info(f"  NDCG@10:  {metrics.ndcg_at_10:.4f}")
        logger.info(f"  NDCG@50:  {metrics.ndcg_at_50:.4f}")

        logger.info("\n🎯 Classification Metrics:")
        logger.info(f"  Precision: {metrics.precision:.4f}")
        logger.info(f"  Recall:    {metrics.recall:.4f}")
        logger.info(f"  F1 Score:  {metrics.f1_score:.4f}")

        logger.info("\n✨ Content Quality:")
        logger.info(f"  Hook Score:      {metrics.avg_hook_score:.4f}")
        logger.info(f"  Structure Score: {metrics.avg_structure_score:.4f}")
        logger.info(f"  Emotion Score:   {metrics.avg_emotion_score:.4f}")

        logger.info("\n🌈 Diversity:")
        logger.info(f"  Unique Ratio:     {metrics.unique_ratio:.4f}")
        logger.info(f"  Vocab Diversity:  {metrics.vocab_diversity:.4f}")

        logger.info("=" * 60)

    def save_metrics(self, metrics: EvaluationMetrics, output_path: str):
        """保存评估结果"""
        metrics_dict = {
            "ndcg_at_10": metrics.ndcg_at_10,
            "ndcg_at_50": metrics.ndcg_at_50,
            "precision": metrics.precision,
            "recall": metrics.recall,
            "f1_score": metrics.f1_score,
            "avg_hook_score": metrics.avg_hook_score,
            "avg_structure_score": metrics.avg_structure_score,
            "avg_emotion_score": metrics.avg_emotion_score,
            "unique_ratio": metrics.unique_ratio,
            "vocab_diversity": metrics.vocab_diversity
        }

        with open(output_path, "w") as f:
            json.dump(metrics_dict, f, indent=2)

        logger.info(f"Metrics saved to {output_path}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="Model Evaluation")
    parser.add_argument("--model-path", type=str, required=True, help="Path to model")
    parser.add_argument("--test-data", type=str, required=True, help="Path to test data")
    parser.add_argument("--output", type=str, default="./evaluation_results.json", help="Output path")

    args = parser.parse_args()

    # 创建评估器
    evaluator = ModelEvaluator(
        model_path=args.model_path,
        test_data_path=args.test_data
    )

    # 运行评估
    metrics = evaluator.run_full_evaluation()

    # 保存结果
    evaluator.save_metrics(metrics, args.output)


if __name__ == "__main__":
    main()
