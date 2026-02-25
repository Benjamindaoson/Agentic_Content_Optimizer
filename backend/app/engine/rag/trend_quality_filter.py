"""
趋势质量过滤器 - 评估和过滤趋势内容
防止噪声注入和品牌调性崩塌
"""

from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TrendQualityScore:
    """趋势质量评分"""
    freshness: float  # 新鲜度
    credibility: float  # 可信度
    audience_match: float  # 人群匹配度
    brand_fit: float  # 品牌适配度
    total_score: float  # 总分
    details: Dict[str, Any]  # 详细信息


class BrandGuidelines:
    """品牌指南"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}

        # 品牌调性关键词
        self.tone_keywords = config.get('tone_keywords', [])

        # 违禁词
        self.forbidden_words = config.get('forbidden_words', [
            '低俗', '色情', '暴力', '赌博', '欺诈',
            '假货', '盗版', '侵权', '违法', '犯罪'
        ])

        # 品牌价值观
        self.brand_values = config.get('brand_values', [
            '专业', '可信', '创新', '用户至上'
        ])

        # 目标受众特征
        self.target_audience = config.get('target_audience', {
            'age_range': [18, 45],
            'interests': [],
            'pain_points': []
        })

    def check_compliance(self, content: str) -> tuple[bool, List[str]]:
        """检查合规性"""
        violations = []

        for word in self.forbidden_words:
            if word in content:
                violations.append(f"包含违禁词: {word}")

        return len(violations) == 0, violations

    def calculate_tone_match(self, content: str) -> float:
        """计算调性匹配度"""
        if not self.tone_keywords:
            return 0.5

        matches = sum(1 for keyword in self.tone_keywords if keyword in content)
        return min(matches / len(self.tone_keywords), 1.0)


class TrendQualityFilter:
    """
    趋势质量过滤器

    功能：
    1. 评估趋势的新鲜度、可信度、人群匹配度、品牌适配度
    2. 过滤低质量趋势
    3. 为趋势打分排序
    """

    def __init__(
        self,
        brand_guidelines: Optional[BrandGuidelines] = None,
        weights: Optional[Dict[str, float]] = None
    ):
        """
        初始化趋势质量过滤器

        Args:
            brand_guidelines: 品牌指南
            weights: 各维度权重
        """
        self.brand_guidelines = brand_guidelines or BrandGuidelines()

        self.weights = weights or {
            'freshness': 0.2,
            'credibility': 0.2,
            'audience_match': 0.3,
            'brand_fit': 0.3
        }

        logger.info("Trend Quality Filter initialized")

    def score_trend(
        self,
        trend: Dict[str, Any],
        target_audience: Optional[Dict[str, Any]] = None
    ) -> TrendQualityScore:
        """
        给趋势打分

        Args:
            trend: 趋势数据
            target_audience: 目标受众（可选，覆盖默认）

        Returns:
            TrendQualityScore
        """

        # 1. 新鲜度
        freshness = self._calculate_freshness(trend)

        # 2. 可信度
        credibility = self._calculate_credibility(trend)

        # 3. 人群匹配度
        audience_match = self._calculate_audience_match(
            trend,
            target_audience or self.brand_guidelines.target_audience
        )

        # 4. 品牌适配度
        brand_fit = self._calculate_brand_fit(trend)

        # 5. 加权总分
        total_score = (
            freshness * self.weights['freshness'] +
            credibility * self.weights['credibility'] +
            audience_match * self.weights['audience_match'] +
            brand_fit * self.weights['brand_fit']
        )

        return TrendQualityScore(
            freshness=round(freshness, 3),
            credibility=round(credibility, 3),
            audience_match=round(audience_match, 3),
            brand_fit=round(brand_fit, 3),
            total_score=round(total_score, 3),
            details={
                'weights': self.weights,
                'trend_id': trend.get('id', 'unknown')
            }
        )

    def filter_trends(
        self,
        trends: List[Dict[str, Any]],
        threshold: float = 0.6,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        过滤和排序趋势

        Args:
            trends: 趋势列表
            threshold: 质量阈值
            max_results: 最多返回数量

        Returns:
            过滤后的趋势列表（按质量排序）
        """

        filtered = []

        for trend in trends:
            # 评分
            score = self.score_trend(trend)

            # 过滤低质量
            if score.total_score >= threshold:
                trend['quality_score'] = score.total_score
                trend['quality_details'] = {
                    'freshness': score.freshness,
                    'credibility': score.credibility,
                    'audience_match': score.audience_match,
                    'brand_fit': score.brand_fit
                }
                filtered.append(trend)

        # 排序
        filtered.sort(key=lambda x: x['quality_score'], reverse=True)

        # 限制数量
        result = filtered[:max_results]

        logger.info(
            f"Filtered trends: {len(trends)} -> {len(filtered)} -> {len(result)} "
            f"(threshold={threshold})"
        )

        return result

    def _calculate_freshness(self, trend: Dict[str, Any]) -> float:
        """计算新鲜度（时间衰减）"""

        publish_time = trend.get('publish_time')
        if not publish_time:
            return 0.5  # 未知时间，给中等分

        # 解析时间
        if isinstance(publish_time, str):
            try:
                publish_time = datetime.fromisoformat(publish_time.replace('Z', '+00:00'))
            except:
                return 0.5

        # 计算时间差
        now = datetime.now(publish_time.tzinfo) if publish_time.tzinfo else datetime.now()
        time_diff = now - publish_time
        hours_ago = time_diff.total_seconds() / 3600

        # 时间衰减函数
        # 0-24小时: 1.0
        # 24-72小时: 0.8
        # 72-168小时(1周): 0.5
        # >1周: 0.2
        if hours_ago <= 24:
            return 1.0
        elif hours_ago <= 72:
            return 0.8
        elif hours_ago <= 168:
            return 0.5
        else:
            return 0.2

    def _calculate_credibility(self, trend: Dict[str, Any]) -> float:
        """计算可信度（来源 + 作者权威）"""

        score = 0.5  # 基础分

        # 1. 平台权重
        platform = trend.get('platform', '').lower()
        platform_weights = {
            'xiaohongshu': 0.9,
            'douyin': 0.85,
            'tiktok': 0.8,
            'weibo': 0.75,
            'bilibili': 0.85
        }
        platform_score = platform_weights.get(platform, 0.5)

        # 2. 作者权威（粉丝数、认证状态）
        author_info = trend.get('author', {})
        followers = author_info.get('followers', 0)
        is_verified = author_info.get('verified', False)

        # 粉丝数评分（对数缩放）
        if followers > 0:
            follower_score = min(np.log10(followers) / 7, 1.0)  # 1000万粉丝 = 1.0
        else:
            follower_score = 0.3

        # 认证加分
        verified_bonus = 0.2 if is_verified else 0

        # 3. 互动数据（点赞、评论、分享）
        engagement = trend.get('engagement', {})
        likes = engagement.get('likes', 0)
        comments = engagement.get('comments', 0)
        shares = engagement.get('shares', 0)

        # 互动率评分
        total_engagement = likes + comments * 10 + shares * 20
        if total_engagement > 0:
            engagement_score = min(np.log10(total_engagement) / 6, 1.0)
        else:
            engagement_score = 0.3

        # 综合可信度
        credibility = (
            platform_score * 0.3 +
            follower_score * 0.3 +
            engagement_score * 0.3 +
            verified_bonus +
            0.1  # 基础分
        )

        return min(credibility, 1.0)

    def _calculate_audience_match(
        self,
        trend: Dict[str, Any],
        target_audience: Dict[str, Any]
    ) -> float:
        """计算人群匹配度"""

        # 简化版：基于关键词匹配
        content = trend.get('content', '') or trend.get('description', '')

        # 1. 兴趣匹配
        interests = target_audience.get('interests', [])
        if interests:
            interest_matches = sum(1 for interest in interests if interest in content)
            interest_score = min(interest_matches / len(interests), 1.0)
        else:
            interest_score = 0.5

        # 2. 痛点匹配
        pain_points = target_audience.get('pain_points', [])
        if pain_points:
            pain_matches = sum(1 for pain in pain_points if pain in content)
            pain_score = min(pain_matches / len(pain_points), 1.0)
        else:
            pain_score = 0.5

        # 3. 年龄段适配（基于内容风格推断）
        age_range = target_audience.get('age_range', [18, 45])
        age_score = self._infer_age_appropriateness(content, age_range)

        # 综合匹配度
        audience_match = (
            interest_score * 0.4 +
            pain_score * 0.4 +
            age_score * 0.2
        )

        return audience_match

    def _infer_age_appropriateness(self, content: str, age_range: List[int]) -> float:
        """推断内容对年龄段的适配度"""

        # 简化版：基于关键词
        young_keywords = ['潮流', '酷', '炸裂', '绝绝子', 'yyds', '冲']
        mature_keywords = ['专业', '深度', '分析', '经验', '建议', '理性']

        young_count = sum(1 for kw in young_keywords if kw in content)
        mature_count = sum(1 for kw in mature_keywords if kw in content)

        # 根据目标年龄段判断
        target_age = (age_range[0] + age_range[1]) / 2

        if target_age < 25:
            # 年轻受众，偏好年轻化内容
            return 0.7 + 0.3 * (young_count / max(young_count + mature_count, 1))
        elif target_age > 35:
            # 成熟受众，偏好专业内容
            return 0.7 + 0.3 * (mature_count / max(young_count + mature_count, 1))
        else:
            # 中间受众，平衡即可
            return 0.8

    def _calculate_brand_fit(self, trend: Dict[str, Any]) -> float:
        """计算品牌适配度"""

        content = trend.get('content', '') or trend.get('description', '')

        # 1. 合规性检查
        is_compliant, violations = self.brand_guidelines.check_compliance(content)
        if not is_compliant:
            logger.warning(f"Trend compliance violations: {violations}")
            return 0.0  # 不合规直接零分

        # 2. 调性匹配
        tone_match = self.brand_guidelines.calculate_tone_match(content)

        # 3. 价值观匹配
        value_matches = sum(
            1 for value in self.brand_guidelines.brand_values
            if value in content
        )
        value_score = min(value_matches / max(len(self.brand_guidelines.brand_values), 1), 1.0)

        # 4. 负面内容检测
        negative_keywords = ['差评', '投诉', '退款', '骗', '假', '坑']
        has_negative = any(kw in content for kw in negative_keywords)
        negative_penalty = 0.3 if has_negative else 0

        # 综合品牌适配度
        brand_fit = (
            tone_match * 0.4 +
            value_score * 0.3 +
            0.3  # 基础分
        ) - negative_penalty

        return max(brand_fit, 0)


class TrendRelevanceRanker:
    """趋势相关性排序器"""

    def __init__(self, quality_filter: TrendQualityFilter):
        self.quality_filter = quality_filter

    def rank_trends(
        self,
        trends: List[Dict[str, Any]],
        query: str,
        target_audience: Optional[Dict[str, Any]] = None,
        strategy: str = 'balanced'  # 'quality', 'relevance', 'balanced'
    ) -> List[Dict[str, Any]]:
        """
        排序趋势

        Args:
            trends: 趋势列表
            query: 查询关键词
            target_audience: 目标受众
            strategy: 排序策略

        Returns:
            排序后的趋势列表
        """

        ranked = []

        for trend in trends:
            # 质量评分
            quality_score = self.quality_filter.score_trend(trend, target_audience)

            # 相关性评分（简单的关键词匹配）
            content = trend.get('content', '') or trend.get('description', '')
            relevance_score = self._calculate_relevance(content, query)

            # 综合评分
            if strategy == 'quality':
                final_score = quality_score.total_score
            elif strategy == 'relevance':
                final_score = relevance_score
            else:  # balanced
                final_score = 0.6 * quality_score.total_score + 0.4 * relevance_score

            trend['final_score'] = final_score
            trend['quality_score'] = quality_score.total_score
            trend['relevance_score'] = relevance_score

            ranked.append(trend)

        # 排序
        ranked.sort(key=lambda x: x['final_score'], reverse=True)

        return ranked

    def _calculate_relevance(self, content: str, query: str) -> float:
        """计算相关性"""

        # 简化版：关键词匹配
        query_words = set(query.split())
        content_words = set(content)

        if not query_words:
            return 0.5

        matches = len(query_words & content_words)
        relevance = matches / len(query_words)

        return min(relevance, 1.0)
