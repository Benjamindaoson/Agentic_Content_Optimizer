"""
GEO 评分计算模块
GEO_score = 0.4 * Structure_Clarity + 0.4 * Keyword_Coverage + 0.2 * Summary_Recall
"""

import re
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class GEOScore:
    """GEO 评分结果"""
    structure_clarity: float  # 结构清晰度
    keyword_coverage: float  # 关键词覆盖率
    summary_recall: float  # 摘要还原度
    total_score: float  # 总分


class StructureClarityCalculator:
    """结构清晰度计算器"""

    def __init__(self, llm_model=None):
        self.llm_model = llm_model

    def calculate(self, content: Dict) -> float:
        """
        计算结构清晰度
        通过 LLM 解析结构的成功率
        """

        # 1. 检查是否有明确的 Hook/Body/CTA 结构
        has_hook = bool(content.get("hook"))
        has_body = bool(content.get("body"))
        has_cta = bool(content.get("cta"))

        if not (has_hook and has_body and has_cta):
            return 0.0

        # 2. 检查结构完整性
        hook = content["hook"]
        body = content["body"]
        cta = content["cta"]

        # Hook 应该简短有力（10-50字）
        hook_score = 1.0 if 10 <= len(hook) <= 50 else 0.5

        # Body 应该有分点表达（检查是否有数字、符号分隔）
        body_has_structure = bool(re.search(r'[1-9][\.\、]|[①-⑨]|•|▪', body))
        body_score = 1.0 if body_has_structure else 0.5

        # CTA 应该有明确的行动指令
        cta_keywords = ['点赞', '关注', '评论', '分享', '收藏', '转发', '私信', '购买']
        cta_has_action = any(keyword in cta for keyword in cta_keywords)
        cta_score = 1.0 if cta_has_action else 0.5

        # 3. 综合评分
        structure_clarity = (hook_score + body_score + cta_score) / 3.0

        return structure_clarity


class KeywordCoverageCalculator:
    """关键词覆盖率计算器"""

    def calculate(self, content: Dict, geo_keywords: List[str]) -> float:
        """
        计算关键词覆盖率
        检查 GEO 关键词在内容中的命中率
        """

        if not geo_keywords:
            return 0.0

        # 合并所有文本
        full_text = ""
        if content.get("hook"):
            full_text += content["hook"]
        if content.get("body"):
            full_text += content["body"]
        if content.get("cta"):
            full_text += content["cta"]

        # 计算命中的关键词数量
        hit_count = 0
        for keyword in geo_keywords:
            if keyword in full_text:
                hit_count += 1

        # 覆盖率
        coverage = hit_count / len(geo_keywords)

        return coverage


class SummaryRecallCalculator:
    """摘要还原度计算器"""

    def __init__(self, llm_model=None, tokenizer=None):
        self.llm_model = llm_model
        self.tokenizer = tokenizer

    def calculate(self, content: Dict) -> float:
        """
        计算摘要还原度
        通过 LLM 生成摘要，然后计算与原文的相似度
        """

        # 合并所有文本
        full_text = ""
        if content.get("hook"):
            full_text += content["hook"] + "\n"
        if content.get("body"):
            full_text += content["body"] + "\n"
        if content.get("cta"):
            full_text += content["cta"]

        if not full_text.strip():
            return 0.0

        # 简化版：检查关键信息是否完整
        # 1. Hook 的核心观点是否在 Body 中展开
        # 2. Body 的要点是否在 CTA 中呼应

        hook = content.get("hook", "")
        body = content.get("body", "")
        cta = content.get("cta", "")

        # 提取 Hook 中的关键词（去除标点）
        hook_keywords = set(re.findall(r'[\u4e00-\u9fa5]{2,}', hook))

        # 检查 Body 中是否包含 Hook 的关键词
        body_contains_hook = sum(1 for kw in hook_keywords if kw in body)
        hook_recall = body_contains_hook / len(hook_keywords) if hook_keywords else 0.0

        # 提取 Body 中的关键词
        body_keywords = set(re.findall(r'[\u4e00-\u9fa5]{2,}', body))

        # 检查 CTA 中是否呼应 Body
        cta_contains_body = sum(1 for kw in body_keywords if kw in cta)
        body_recall = min(cta_contains_body / len(body_keywords), 1.0) if body_keywords else 0.0

        # 综合还原度
        summary_recall = (hook_recall + body_recall) / 2.0

        return summary_recall


class GEOScoreCalculator:
    """GEO 评分计算器"""

    def __init__(
        self,
        llm_model=None,
        tokenizer=None,
        weights: Optional[Dict[str, float]] = None
    ):
        self.llm_model = llm_model
        self.tokenizer = tokenizer

        # 默认权重
        self.weights = weights or {
            "structure_clarity": 0.4,
            "keyword_coverage": 0.4,
            "summary_recall": 0.2
        }

        # 初始化子计算器
        self.structure_calculator = StructureClarityCalculator(llm_model)
        self.keyword_calculator = KeywordCoverageCalculator()
        self.summary_calculator = SummaryRecallCalculator(llm_model, tokenizer)

    def calculate(
        self,
        content: Dict,
        geo_keywords: List[str]
    ) -> GEOScore:
        """
        计算 GEO 评分
        GEO_score = 0.4 * Structure_Clarity + 0.4 * Keyword_Coverage + 0.2 * Summary_Recall
        """

        # 1. 结构清晰度
        structure_clarity = self.structure_calculator.calculate(content)

        # 2. 关键词覆盖率
        keyword_coverage = self.keyword_calculator.calculate(content, geo_keywords)

        # 3. 摘要还原度
        summary_recall = self.summary_calculator.calculate(content)

        # 4. 综合评分
        total_score = (
            self.weights["structure_clarity"] * structure_clarity +
            self.weights["keyword_coverage"] * keyword_coverage +
            self.weights["summary_recall"] * summary_recall
        )

        return GEOScore(
            structure_clarity=structure_clarity,
            keyword_coverage=keyword_coverage,
            summary_recall=summary_recall,
            total_score=total_score
        )

    def calculate_batch(
        self,
        contents: List[Dict],
        geo_keywords: List[str]
    ) -> List[GEOScore]:
        """批量计算 GEO 评分"""
        scores = []
        for content in contents:
            score = self.calculate(content, geo_keywords)
            scores.append(score)

        return scores


def main():
    """测试 GEO 评分计算"""

    # 测试内容
    content = {
        "hook": "3个技巧让你的短视频播放量翻10倍！",
        "body": """1. 前3秒抓眼球：用反常识观点或数据震撼
2. 中间加悬念：设置问题让观众想看答案
3. 结尾强互动：引导点赞评论分享""",
        "cta": "学会这3招，你的视频也能爆！快点赞收藏试试看！"
    }

    # GEO 关键词
    geo_keywords = ["短视频", "播放量", "技巧", "互动", "点赞"]

    # 计算 GEO 评分
    calculator = GEOScoreCalculator()
    score = calculator.calculate(content, geo_keywords)

    print("=" * 60)
    print("GEO Score Calculation Result")
    print("=" * 60)
    print(f"Structure Clarity:  {score.structure_clarity:.3f}")
    print(f"Keyword Coverage:   {score.keyword_coverage:.3f}")
    print(f"Summary Recall:     {score.summary_recall:.3f}")
    print(f"Total Score:        {score.total_score:.3f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
