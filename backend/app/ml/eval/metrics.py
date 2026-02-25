"""
Metrics Calculator

计算各种评估指标
"""

from typing import Dict, List, Any, Optional
import numpy as np
from collections import Counter
import logging

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """指标计算器"""

    @staticmethod
    def calculate_perplexity(loss: float) -> float:
        """计算困惑度"""
        return np.exp(loss)

    @staticmethod
    def calculate_bleu(references: List[str], hypothesis: str) -> float:
        """计算 BLEU 分数（简化版）"""
        from collections import Counter

        # 简化的 BLEU-1 实现
        ref_tokens = set(references[0].split())
        hyp_tokens = hypothesis.split()

        matches = sum(1 for token in hyp_tokens if token in ref_tokens)
        precision = matches / len(hyp_tokens) if hyp_tokens else 0.0

        # 简单的长度惩罚
        bp = min(1.0, len(hyp_tokens) / len(references[0].split()))

        return precision * bp

    @staticmethod
    def calculate_rouge_l(reference: str, hypothesis: str) -> float:
        """计算 ROUGE-L 分数"""
        ref_tokens = reference.split()
        hyp_tokens = hypothesis.split()

        # 计算最长公共子序列
        m, n = len(ref_tokens), len(hyp_tokens)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if ref_tokens[i - 1] == hyp_tokens[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

        lcs_length = dp[m][n]

        # 计算 precision 和 recall
        precision = lcs_length / n if n > 0 else 0.0
        recall = lcs_length / m if m > 0 else 0.0

        # F1 score
        if precision + recall > 0:
            f1 = 2 * precision * recall / (precision + recall)
        else:
            f1 = 0.0

        return f1

    @staticmethod
    def calculate_diversity(texts: List[str]) -> Dict[str, float]:
        """计算文本多样性"""
        all_tokens = []
        for text in texts:
            all_tokens.extend(text.split())

        if not all_tokens:
            return {"distinct-1": 0.0, "distinct-2": 0.0}

        # Distinct-1: 不同 unigram 的比例
        unigrams = all_tokens
        distinct_1 = len(set(unigrams)) / len(unigrams) if unigrams else 0.0

        # Distinct-2: 不同 bigram 的比例
        bigrams = [f"{unigrams[i]}_{unigrams[i+1]}" for i in range(len(unigrams) - 1)]
        distinct_2 = len(set(bigrams)) / len(bigrams) if bigrams else 0.0

        return {
            "distinct-1": distinct_1,
            "distinct-2": distinct_2,
        }

    @staticmethod
    def calculate_length_stats(texts: List[str]) -> Dict[str, float]:
        """计算长度统计"""
        lengths = [len(text.split()) for text in texts]

        if not lengths:
            return {"mean": 0.0, "std": 0.0, "min": 0, "max": 0}

        return {
            "mean": np.mean(lengths),
            "std": np.std(lengths),
            "min": min(lengths),
            "max": max(lengths),
        }

    @staticmethod
    def calculate_platform_fit(text: str, platform: str) -> float:
        """计算平台适配度（简化版）"""
        # 小红书特征
        if platform == "xiaohongshu":
            score = 0.0

            # 表情符号
            emoji_count = sum(1 for char in text if ord(char) > 0x1F300)
            if emoji_count > 0:
                score += 0.3

            # 标签
            if "#" in text:
                score += 0.2

            # 长度（小红书偏好 500-1000 字）
            length = len(text)
            if 500 <= length <= 1000:
                score += 0.3
            elif 300 <= length < 500 or 1000 < length <= 1500:
                score += 0.15

            # 段落结构
            paragraphs = text.split("\n\n")
            if 3 <= len(paragraphs) <= 8:
                score += 0.2

            return min(score, 1.0)

        # 抖音特征
        elif platform == "douyin":
            score = 0.0

            # 短小精悍（抖音偏好 100-300 字）
            length = len(text)
            if 100 <= length <= 300:
                score += 0.4
            elif 50 <= length < 100 or 300 < length <= 500:
                score += 0.2

            # 话题标签
            if "#" in text:
                score += 0.3

            # 互动引导
            interaction_keywords = ["点赞", "关注", "评论", "转发", "收藏"]
            if any(kw in text for kw in interaction_keywords):
                score += 0.3

            return min(score, 1.0)

        return 0.5  # 默认分数

    @staticmethod
    def calculate_engagement_potential(text: str, platform: str) -> float:
        """计算互动潜力（简化版）"""
        score = 0.0

        # 情感词
        positive_words = ["好", "棒", "赞", "爱", "喜欢", "推荐", "必备", "神器"]
        negative_words = ["差", "烂", "坑", "骗", "假"]

        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)

        if positive_count > negative_count:
            score += 0.3

        # 疑问句（引发讨论）
        if "?" in text or "？" in text:
            score += 0.2

        # 数字和数据（增加可信度）
        import re
        numbers = re.findall(r'\d+', text)
        if len(numbers) >= 3:
            score += 0.2

        # 个人经历（增加共鸣）
        experience_keywords = ["我", "自己", "亲测", "体验", "感受"]
        if any(kw in text for kw in experience_keywords):
            score += 0.3

        return min(score, 1.0)

    @staticmethod
    def calculate_all_metrics(
        generated_texts: List[str],
        reference_texts: Optional[List[str]] = None,
        platform: Optional[str] = None,
    ) -> Dict[str, Any]:
        """计算所有指标"""
        metrics = {}

        # 多样性指标
        diversity = MetricsCalculator.calculate_diversity(generated_texts)
        metrics.update(diversity)

        # 长度统计
        length_stats = MetricsCalculator.calculate_length_stats(generated_texts)
        metrics["length"] = length_stats

        # 如果有参考文本，计算 BLEU 和 ROUGE
        if reference_texts:
            bleu_scores = []
            rouge_scores = []

            for gen, ref in zip(generated_texts, reference_texts):
                bleu = MetricsCalculator.calculate_bleu([ref], gen)
                rouge = MetricsCalculator.calculate_rouge_l(ref, gen)

                bleu_scores.append(bleu)
                rouge_scores.append(rouge)

            metrics["bleu"] = np.mean(bleu_scores)
            metrics["rouge-l"] = np.mean(rouge_scores)

        # 平台适配度
        if platform:
            platform_fit_scores = [
                MetricsCalculator.calculate_platform_fit(text, platform)
                for text in generated_texts
            ]
            metrics["platform_fit"] = np.mean(platform_fit_scores)

            engagement_scores = [
                MetricsCalculator.calculate_engagement_potential(text, platform)
                for text in generated_texts
            ]
            metrics["engagement_potential"] = np.mean(engagement_scores)

        return metrics
