"""
策略约束层

用于控制内容生成策略，支持品牌调性、行业边界、多目标优化
"""

import logging
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from enum import Enum
import re

logger = logging.getLogger(__name__)


class ConstraintType(str, Enum):
    """约束类型"""
    REQUIRED = 'required'  # 必须包含
    FORBIDDEN = 'forbidden'  # 禁止包含
    PREFERRED = 'preferred'  # 优先包含
    AVOIDED = 'avoided'  # 尽量避免


@dataclass
class StrategyConstraint:
    """策略约束"""
    # 品牌调性
    brand_voice: Optional[str] = None  # 'professional', 'casual', 'friendly', 'authoritative'
    tone: Optional[str] = None  # 'serious', 'humorous', 'inspirational'

    # 关键词约束
    required_keywords: Set[str] = None  # 必须包含的关键词
    forbidden_keywords: Set[str] = None  # 禁止的关键词
    preferred_keywords: Set[str] = None  # 优先的关键词

    # 结构约束
    min_length: Optional[int] = None  # 最小长度
    max_length: Optional[int] = None  # 最大长度
    required_sections: Optional[List[str]] = None  # 必须的章节
    forbidden_patterns: Optional[List[str]] = None  # 禁止的模式

    # 受众约束
    target_audience: Optional[str] = None  # 目标受众
    age_range: Optional[tuple] = None  # 年龄范围
    gender: Optional[str] = None  # 性别

    # 行业约束
    industry: Optional[str] = None  # 行业
    compliance_rules: Optional[List[str]] = None  # 合规规则

    def __post_init__(self):
        if self.required_keywords is None:
            self.required_keywords = set()
        if self.forbidden_keywords is None:
            self.forbidden_keywords = set()
        if self.preferred_keywords is None:
            self.preferred_keywords = set()


@dataclass
class OptimizationObjective:
    """优化目标"""
    name: str  # 目标名称
    weight: float  # 权重
    target_value: Optional[float] = None  # 目标值
    min_value: Optional[float] = None  # 最小值
    max_value: Optional[float] = None  # 最大值


class StrategyController:
    """
    策略控制器

    功能：
    1. 策略约束验证
    2. 多目标优化
    3. 预算约束
    4. 内容过滤
    """

    def __init__(
        self,
        constraint: StrategyConstraint,
        objectives: Optional[List[OptimizationObjective]] = None,
        budget_limit: Optional[Dict] = None
    ):
        self.constraint = constraint
        self.objectives = objectives or []
        self.budget_limit = budget_limit or {}

    def validate_content(self, title: str, text: str) -> tuple[bool, List[str]]:
        """
        验证内容是否符合约束

        Args:
            title: 标题
            text: 正文

        Returns:
            (是否通过, 违规原因列表)
        """
        violations = []
        content = title + ' ' + text

        # 1. 检查必须关键词
        if self.constraint.required_keywords:
            missing = [
                kw for kw in self.constraint.required_keywords
                if kw not in content
            ]
            if missing:
                violations.append(f"缺少必须关键词: {', '.join(missing)}")

        # 2. 检查禁止关键词
        if self.constraint.forbidden_keywords:
            found = [
                kw for kw in self.constraint.forbidden_keywords
                if kw in content
            ]
            if found:
                violations.append(f"包含禁止关键词: {', '.join(found)}")

        # 3. 检查长度约束
        total_length = len(title) + len(text)

        if self.constraint.min_length and total_length < self.constraint.min_length:
            violations.append(f"内容过短: {total_length} < {self.constraint.min_length}")

        if self.constraint.max_length and total_length > self.constraint.max_length:
            violations.append(f"内容过长: {total_length} > {self.constraint.max_length}")

        # 4. 检查禁止模式
        if self.constraint.forbidden_patterns:
            for pattern in self.constraint.forbidden_patterns:
                if re.search(pattern, content):
                    violations.append(f"包含禁止模式: {pattern}")

        # 5. 检查必须章节
        if self.constraint.required_sections:
            for section in self.constraint.required_sections:
                if section not in text:
                    violations.append(f"缺少必须章节: {section}")

        is_valid = len(violations) == 0

        return is_valid, violations

    def calculate_multi_objective_score(
        self,
        metrics: Dict[str, float]
    ) -> float:
        """
        计算多目标优化分数

        Args:
            metrics: 指标字典

        Returns:
            综合分数
        """
        if not self.objectives:
            return 0.0

        total_score = 0.0
        total_weight = sum(obj.weight for obj in self.objectives)

        for objective in self.objectives:
            metric_value = metrics.get(objective.name, 0.0)

            # 归一化到 [0, 1]
            if objective.min_value is not None and objective.max_value is not None:
                normalized = (metric_value - objective.min_value) / (objective.max_value - objective.min_value)
                normalized = max(0.0, min(1.0, normalized))
            else:
                normalized = metric_value

            # 如果有目标值，计算接近度
            if objective.target_value is not None:
                distance = abs(normalized - objective.target_value)
                score = 1.0 - distance
            else:
                score = normalized

            total_score += score * objective.weight

        return total_score / total_weight if total_weight > 0 else 0.0

    def check_budget(
        self,
        current_usage: Dict[str, float]
    ) -> tuple[bool, List[str]]:
        """
        检查预算约束

        Args:
            current_usage: 当前使用量

        Returns:
            (是否在预算内, 超预算项列表)
        """
        over_budget = []

        for resource, limit in self.budget_limit.items():
            usage = current_usage.get(resource, 0.0)

            if usage > limit:
                over_budget.append(f"{resource}: {usage} > {limit}")

        is_within_budget = len(over_budget) == 0

        return is_within_budget, over_budget

    def apply_preference_boost(
        self,
        title: str,
        text: str,
        base_score: float
    ) -> float:
        """
        应用偏好加成

        Args:
            title: 标题
            text: 正文
            base_score: 基础分数

        Returns:
            调整后的分数
        """
        content = title + ' ' + text
        boost = 0.0

        # 优先关键词加成
        if self.constraint.preferred_keywords:
            matched = sum(
                1 for kw in self.constraint.preferred_keywords
                if kw in content
            )
            boost += matched * 0.05  # 每个优先关键词 +5%

        return base_score * (1.0 + boost)


class RewardDefenseSystem:
    """
    奖励函数防劫持系统

    功能：
    1. 检测关键词堆砌
    2. 检测结构模板化
    3. 检测过度重复
    4. 惩罚项计算
    """

    def __init__(
        self,
        keyword_density_threshold: float = 0.05,  # 关键词密度阈值
        ngram_repeat_threshold: int = 3,  # n-gram 重复阈值
        template_similarity_threshold: float = 0.8  # 模板相似度阈值
    ):
        self.keyword_density_threshold = keyword_density_threshold
        self.ngram_repeat_threshold = ngram_repeat_threshold
        self.template_similarity_threshold = template_similarity_threshold

    def detect_keyword_stuffing(
        self,
        text: str,
        keywords: List[str]
    ) -> tuple[bool, float]:
        """
        检测关键词堆砌

        Args:
            text: 文本
            keywords: 关键词列表

        Returns:
            (是否堆砌, 密度)
        """
        if not keywords:
            return False, 0.0

        total_words = len(text.split())
        if total_words == 0:
            return False, 0.0

        keyword_count = sum(text.count(kw) for kw in keywords)
        density = keyword_count / total_words

        is_stuffing = density > self.keyword_density_threshold

        return is_stuffing, density

    def detect_ngram_repetition(
        self,
        text: str,
        n: int = 3
    ) -> tuple[bool, int]:
        """
        检测 n-gram 重复

        Args:
            text: 文本
            n: n-gram 大小

        Returns:
            (是否过度重复, 最大重复次数)
        """
        words = text.split()

        if len(words) < n:
            return False, 0

        ngrams = {}
        for i in range(len(words) - n + 1):
            ngram = ' '.join(words[i:i+n])
            ngrams[ngram] = ngrams.get(ngram, 0) + 1

        max_repeat = max(ngrams.values()) if ngrams else 0

        is_repetitive = max_repeat > self.ngram_repeat_threshold

        return is_repetitive, max_repeat

    def detect_template_overuse(
        self,
        text: str,
        templates: List[str]
    ) -> tuple[bool, float]:
        """
        检测模板过度使用

        Args:
            text: 文本
            templates: 模板列表

        Returns:
            (是否过度模板化, 最大相似度)
        """
        if not templates:
            return False, 0.0

        max_similarity = 0.0

        for template in templates:
            similarity = self._calculate_similarity(text, template)
            max_similarity = max(max_similarity, similarity)

        is_overused = max_similarity > self.template_similarity_threshold

        return is_overused, max_similarity

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度（简化版）"""
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)

    def calculate_penalty(
        self,
        text: str,
        keywords: Optional[List[str]] = None,
        templates: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """
        计算惩罚项

        Args:
            text: 文本
            keywords: 关键词列表
            templates: 模板列表

        Returns:
            惩罚项字典
        """
        penalties = {
            'keyword_stuffing': 0.0,
            'ngram_repetition': 0.0,
            'template_overuse': 0.0,
            'total': 0.0
        }

        # 1. 关键词堆砌惩罚
        if keywords:
            is_stuffing, density = self.detect_keyword_stuffing(text, keywords)
            if is_stuffing:
                penalties['keyword_stuffing'] = (density - self.keyword_density_threshold) * 2.0

        # 2. n-gram 重复惩罚
        is_repetitive, max_repeat = self.detect_ngram_repetition(text)
        if is_repetitive:
            penalties['ngram_repetition'] = (max_repeat - self.ngram_repeat_threshold) * 0.1

        # 3. 模板过度使用惩罚
        if templates:
            is_overused, max_similarity = self.detect_template_overuse(text, templates)
            if is_overused:
                penalties['template_overuse'] = (max_similarity - self.template_similarity_threshold) * 0.5

        # 4. 总惩罚
        penalties['total'] = sum([
            penalties['keyword_stuffing'],
            penalties['ngram_repetition'],
            penalties['template_overuse']
        ])

        return penalties


# ==================== 使用示例 ====================

def example_usage():
    """使用示例"""

    # 1. 创建策略约束
    constraint = StrategyConstraint(
        brand_voice='professional',
        tone='inspirational',
        required_keywords={'护肤', '保湿'},
        forbidden_keywords={'最好', '第一', '绝对'},
        min_length=100,
        max_length=1000,
        target_audience='18-25岁女性',
        industry='美妆'
    )

    # 2. 创建优化目标
    objectives = [
        OptimizationObjective(name='viral_score', weight=0.4, min_value=0.0, max_value=1.0),
        OptimizationObjective(name='engagement_rate', weight=0.3, min_value=0.0, max_value=0.5),
        OptimizationObjective(name='conversion_rate', weight=0.3, min_value=0.0, max_value=0.1)
    ]

    # 3. 创建策略控制器
    controller = StrategyController(
        constraint=constraint,
        objectives=objectives,
        budget_limit={'llm_calls': 1000, 'cost_usd': 50.0}
    )

    # 4. 验证内容
    title = "冬季护肤秘籍"
    text = "保湿是冬季护肤的关键..."

    is_valid, violations = controller.validate_content(title, text)
    print(f"内容验证: {is_valid}, 违规: {violations}")

    # 5. 计算多目标分数
    metrics = {
        'viral_score': 0.8,
        'engagement_rate': 0.12,
        'conversion_rate': 0.05
    }

    score = controller.calculate_multi_objective_score(metrics)
    print(f"多目标分数: {score:.4f}")

    # 6. 创建防劫持系统
    defense = RewardDefenseSystem()

    # 7. 检测关键词堆砌
    is_stuffing, density = defense.detect_keyword_stuffing(
        text="护肤护肤护肤保湿保湿保湿",
        keywords=['护肤', '保湿']
    )
    print(f"关键词堆砌: {is_stuffing}, 密度: {density:.4f}")

    # 8. 计算惩罚
    penalties = defense.calculate_penalty(
        text="护肤护肤护肤保湿保湿保湿",
        keywords=['护肤', '保湿']
    )
    print(f"惩罚项: {penalties}")

    # 9. 应用惩罚后的最终分数
    base_score = 0.8
    final_score = base_score - penalties['total']
    print(f"最终分数: {final_score:.4f}")
