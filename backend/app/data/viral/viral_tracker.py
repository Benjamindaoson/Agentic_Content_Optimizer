"""
病毒式内容追踪器

自动追踪和识别爆款内容
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ViralCriteria:
    """
    爆款判定标准

    三层指标体系：
    1. 绝对指标（Absolute Metrics）- 基础门槛
    2. 相对指标（Relative Metrics）- 同类对比
    3. 速度指标（Velocity Metrics）- 增长速度
    """

    # 绝对指标阈值
    min_views: int = 100000  # 最低播放量
    min_likes: int = 5000    # 最低点赞数
    min_shares: int = 1000   # 最低分享数
    min_comments: int = 500  # 最低评论数

    # 相对指标阈值（百分位）
    views_percentile: float = 0.95  # 播放量需超过 95% 同类内容
    engagement_percentile: float = 0.90  # 互动率需超过 90% 同类内容

    # 速度指标阈值
    min_velocity_score: float = 0.7  # 最低速度分数（0-1）
    velocity_window_hours: int = 24  # 速度计算窗口（小时）

    # 综合权重
    absolute_weight: float = 0.3
    relative_weight: float = 0.4
    velocity_weight: float = 0.3

    # 最终阈值
    min_viral_score: float = 0.75  # 最低爆款分数

    def __post_init__(self):
        """验证权重和为 1.0"""
        total_weight = self.absolute_weight + self.relative_weight + self.velocity_weight
        if not np.isclose(total_weight, 1.0):
            raise ValueError(f"权重和必须为 1.0，当前为 {total_weight}")


@dataclass
class ViralContent:
    """爆款内容数据结构"""

    # 基础信息
    content_id: str
    platform: str  # "tiktok", "xiaohongshu", "douyin"
    content_type: str  # "video", "note", "image"
    text: str
    url: str
    author_id: str
    created_at: datetime
    discovered_at: datetime = field(default_factory=datetime.now)

    # 绝对指标
    views: int = 0
    likes: int = 0
    shares: int = 0
    comments: int = 0
    saves: int = 0

    # 相对指标（需要同类数据计算）
    views_percentile: float = 0.0
    engagement_rate: float = 0.0
    engagement_percentile: float = 0.0

    # 速度指标
    velocity_score: float = 0.0
    growth_rate_24h: float = 0.0

    # 综合评分
    viral_score: float = 0.0

    # 元数据
    category: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def calculate_engagement_rate(self) -> float:
        """计算互动率"""
        if self.views == 0:
            return 0.0
        return (self.likes + self.shares + self.comments + self.saves) / self.views

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'content_id': self.content_id,
            'platform': self.platform,
            'content_type': self.content_type,
            'text': self.text,
            'url': self.url,
            'author_id': self.author_id,
            'created_at': self.created_at.isoformat(),
            'discovered_at': self.discovered_at.isoformat(),
            'metrics': {
                'views': self.views,
                'likes': self.likes,
                'shares': self.shares,
                'comments': self.comments,
                'saves': self.saves,
                'engagement_rate': self.engagement_rate,
            },
            'scores': {
                'views_percentile': self.views_percentile,
                'engagement_percentile': self.engagement_percentile,
                'velocity_score': self.velocity_score,
                'growth_rate_24h': self.growth_rate_24h,
                'viral_score': self.viral_score
            },
            'category': self.category,
            'tags': self.tags,
            'metadata': self.metadata
        }


class ViralContentTracker:
    """
    病毒式内容追踪器

    功能：
    1. 自动追踪平台热门内容
    2. 多维度评分识别爆款
    3. 实时更新爆款库
    4. 提供爆款检索接口
    """

    def __init__(
        self,
        criteria: Optional[ViralCriteria] = None,
        platforms: Optional[List[str]] = None
    ):
        """
        初始化

        Args:
            criteria: 爆款判定标准
            platforms: 追踪的平台列表
        """
        self.criteria = criteria or ViralCriteria()
        self.platforms = platforms or ["tiktok", "xiaohongshu", "douyin"]

        # 爆款内容库
        self.viral_contents: Dict[str, ViralContent] = {}

        # 分类统计（用于计算相对指标）
        self.category_stats: Dict[str, Dict[str, List[float]]] = defaultdict(
            lambda: defaultdict(list)
        )

        # 追踪历史
        self.tracking_history: List[Dict[str, Any]] = []

        logger.info(f"✅ ViralContentTracker 初始化完成，追踪平台: {self.platforms}")

    def track_content(
        self,
        content_id: str,
        platform: str,
        content_type: str,
        text: str,
        url: str,
        author_id: str,
        created_at: datetime,
        metrics: Dict[str, int],
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, float, ViralContent]:
        """
        追踪单条内容

        Args:
            content_id: 内容 ID
            platform: 平台
            content_type: 内容类型
            text: 文本内容
            url: 内容链接
            author_id: 作者 ID
            created_at: 创建时间
            metrics: 指标数据 {'views', 'likes', 'shares', 'comments', 'saves'}
            category: 分类
            tags: 标签
            metadata: 元数据

        Returns:
            (is_viral, viral_score, viral_content)
        """
        # 创建内容对象
        content = ViralContent(
            content_id=content_id,
            platform=platform,
            content_type=content_type,
            text=text,
            url=url,
            author_id=author_id,
            created_at=created_at,
            views=metrics.get('views', 0),
            likes=metrics.get('likes', 0),
            shares=metrics.get('shares', 0),
            comments=metrics.get('comments', 0),
            saves=metrics.get('saves', 0),
            category=category,
            tags=tags or [],
            metadata=metadata or {}
        )

        # 计算互动率
        content.engagement_rate = content.calculate_engagement_rate()

        # 计算相对指标
        if category:
            content.views_percentile = self._calculate_percentile(
                category, 'views', content.views
            )
            content.engagement_percentile = self._calculate_percentile(
                category, 'engagement_rate', content.engagement_rate
            )

        # 计算速度指标
        content.velocity_score = self._calculate_velocity_score(content)
        content.growth_rate_24h = self._calculate_growth_rate(content)

        # 计算综合爆款分数
        content.viral_score = self._calculate_viral_score(content)

        # 判断是否为爆款
        is_viral = self._is_viral(content)

        # 如果是爆款，加入库
        if is_viral:
            self.viral_contents[content_id] = content
            logger.info(
                f"🔥 发现爆款: {content_id} (平台: {platform}, "
                f"分数: {content.viral_score:.3f}, 播放: {content.views:,})"
            )

        # 更新分类统计
        if category:
            self.category_stats[category]['views'].append(content.views)
            self.category_stats[category]['engagement_rate'].append(content.engagement_rate)

        # 记录追踪历史
        self.tracking_history.append({
            'timestamp': datetime.now(),
            'content_id': content_id,
            'is_viral': is_viral,
            'viral_score': content.viral_score
        })

        return is_viral, content.viral_score, content

    def _calculate_percentile(
        self,
        category: str,
        metric: str,
        value: float
    ) -> float:
        """计算百分位"""
        if category not in self.category_stats:
            return 0.5  # 默认中位数

        values = self.category_stats[category].get(metric, [])
        if not values:
            return 0.5

        # 计算百分位
        percentile = np.sum(np.array(values) <= value) / len(values)
        return float(percentile)

    def _calculate_velocity_score(self, content: ViralContent) -> float:
        """
        计算速度分数

        基于内容发布时间和当前指标，估算增长速度
        """
        # 计算发布时长（小时）
        hours_since_creation = (datetime.now() - content.created_at).total_seconds() / 3600

        if hours_since_creation <= 0:
            return 0.0

        # 计算每小时播放量
        views_per_hour = content.views / hours_since_creation

        # 计算每小时互动量
        engagements_per_hour = (
            content.likes + content.shares + content.comments + content.saves
        ) / hours_since_creation

        # 归一化到 [0, 1]
        # 假设 10000 播放/小时 和 500 互动/小时 为满分
        views_score = min(views_per_hour / 10000, 1.0)
        engagement_score = min(engagements_per_hour / 500, 1.0)

        # 加权平均
        velocity_score = 0.6 * views_score + 0.4 * engagement_score

        return float(velocity_score)

    def _calculate_growth_rate(self, content: ViralContent) -> float:
        """
        计算 24 小时增长率

        注：需要历史数据支持，这里简化为基于当前速度的估算
        """
        hours_since_creation = (datetime.now() - content.created_at).total_seconds() / 3600

        if hours_since_creation <= 0:
            return 0.0

        # 如果发布不足 24 小时，估算 24 小时增长率
        if hours_since_creation < 24:
            estimated_24h_views = content.views * (24 / hours_since_creation)
            growth_rate = (estimated_24h_views - content.views) / max(content.views, 1)
        else:
            # 如果超过 24 小时，需要历史数据（这里简化为 0）
            growth_rate = 0.0

        return float(growth_rate)

    def _calculate_viral_score(self, content: ViralContent) -> float:
        """
        计算综合爆款分数

        三层指标加权：
        1. 绝对指标（30%）
        2. 相对指标（40%）
        3. 速度指标（30%）
        """
        # 1. 绝对指标分数
        absolute_score = self._calculate_absolute_score(content)

        # 2. 相对指标分数
        relative_score = self._calculate_relative_score(content)

        # 3. 速度指标分数
        velocity_score = content.velocity_score

        # 加权平均
        viral_score = (
            self.criteria.absolute_weight * absolute_score +
            self.criteria.relative_weight * relative_score +
            self.criteria.velocity_weight * velocity_score
        )

        return float(np.clip(viral_score, 0.0, 1.0))

    def _calculate_absolute_score(self, content: ViralContent) -> float:
        """计算绝对指标分数"""
        scores = []

        # 播放量分数
        if content.views >= self.criteria.min_views:
            scores.append(min(content.views / (self.criteria.min_views * 2), 1.0))
        else:
            scores.append(content.views / self.criteria.min_views)

        # 点赞分数
        if content.likes >= self.criteria.min_likes:
            scores.append(min(content.likes / (self.criteria.min_likes * 2), 1.0))
        else:
            scores.append(content.likes / self.criteria.min_likes)

        # 分享分数
        if content.shares >= self.criteria.min_shares:
            scores.append(min(content.shares / (self.criteria.min_shares * 2), 1.0))
        else:
            scores.append(content.shares / self.criteria.min_shares)

        # 评论分数
        if content.comments >= self.criteria.min_comments:
            scores.append(min(content.comments / (self.criteria.min_comments * 2), 1.0))
        else:
            scores.append(content.comments / self.criteria.min_comments)

        return float(np.mean(scores))

    def _calculate_relative_score(self, content: ViralContent) -> float:
        """计算相对指标分数"""
        if not content.category:
            return 0.5  # 无分类时返回中位数

        # 播放量百分位分数
        views_score = content.views_percentile

        # 互动率百分位分数
        engagement_score = content.engagement_percentile

        # 加权平均
        relative_score = 0.6 * views_score + 0.4 * engagement_score

        return float(relative_score)

    def _is_viral(self, content: ViralContent) -> bool:
        """
        判断是否为爆款

        需要同时满足：
        1. 综合分数 >= 阈值
        2. 绝对指标达标
        3. 相对指标达标（如果有分类）
        """
        # 检查综合分数
        if content.viral_score < self.criteria.min_viral_score:
            return False

        # 检查绝对指标
        if content.views < self.criteria.min_views:
            return False
        if content.likes < self.criteria.min_likes:
            return False
        if content.shares < self.criteria.min_shares:
            return False
        if content.comments < self.criteria.min_comments:
            return False

        # 检查相对指标（如果有分类）
        if content.category:
            if content.views_percentile < self.criteria.views_percentile:
                return False
            if content.engagement_percentile < self.criteria.engagement_percentile:
                return False

        # 检查速度指标
        if content.velocity_score < self.criteria.min_velocity_score:
            return False

        return True

    def get_viral_contents(
        self,
        platform: Optional[str] = None,
        category: Optional[str] = None,
        min_score: Optional[float] = None,
        limit: int = 100,
        sort_by: str = "viral_score"
    ) -> List[ViralContent]:
        """
        获取爆款内容列表

        Args:
            platform: 平台过滤
            category: 分类过滤
            min_score: 最低分数过滤
            limit: 返回数量限制
            sort_by: 排序字段

        Returns:
            爆款内容列表
        """
        contents = list(self.viral_contents.values())

        # 过滤
        if platform:
            contents = [c for c in contents if c.platform == platform]
        if category:
            contents = [c for c in contents if c.category == category]
        if min_score is not None:
            contents = [c for c in contents if c.viral_score >= min_score]

        # 排序
        if sort_by == "viral_score":
            contents.sort(key=lambda c: c.viral_score, reverse=True)
        elif sort_by == "views":
            contents.sort(key=lambda c: c.views, reverse=True)
        elif sort_by == "velocity_score":
            contents.sort(key=lambda c: c.velocity_score, reverse=True)
        elif sort_by == "discovered_at":
            contents.sort(key=lambda c: c.discovered_at, reverse=True)

        return contents[:limit]

    def get_statistics(self) -> Dict[str, Any]:
        """获取追踪统计"""
        total_tracked = len(self.tracking_history)
        total_viral = len(self.viral_contents)
        viral_rate = total_viral / total_tracked if total_tracked > 0 else 0.0

        # 按平台统计
        platform_stats = defaultdict(int)
        for content in self.viral_contents.values():
            platform_stats[content.platform] += 1

        # 按分类统计
        category_stats = defaultdict(int)
        for content in self.viral_contents.values():
            if content.category:
                category_stats[content.category] += 1

        # 平均分数
        if self.viral_contents:
            avg_viral_score = np.mean([c.viral_score for c in self.viral_contents.values()])
            avg_views = np.mean([c.views for c in self.viral_contents.values()])
            avg_engagement_rate = np.mean([c.engagement_rate for c in self.viral_contents.values()])
        else:
            avg_viral_score = 0.0
            avg_views = 0.0
            avg_engagement_rate = 0.0

        return {
            'total_tracked': total_tracked,
            'total_viral': total_viral,
            'viral_rate': viral_rate,
            'platform_distribution': dict(platform_stats),
            'category_distribution': dict(category_stats),
            'average_viral_score': float(avg_viral_score),
            'average_views': float(avg_views),
            'average_engagement_rate': float(avg_engagement_rate)
        }

    def export_viral_contents(self, output_path: str):
        """导出爆款内容到文件"""
        import json

        data = {
            'exported_at': datetime.now().isoformat(),
            'total_count': len(self.viral_contents),
            'contents': [c.to_dict() for c in self.viral_contents.values()]
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ 已导出 {len(self.viral_contents)} 条爆款内容到 {output_path}")
