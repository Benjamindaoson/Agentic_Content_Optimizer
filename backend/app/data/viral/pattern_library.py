"""
爆款模式库

Pattern Library for Viral Content
"""

import logging
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import numpy as np
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ViralPattern:
    """
    爆款模式

    从爆款内容中提取的可复用模式
    """

    # 基础信息
    pattern_id: str
    pattern_type: str  # "hook", "body", "cta", "structure", "emotion", "topic"
    name: str
    description: str
    template: str  # 模板文本（带占位符）
    created_at: datetime = field(default_factory=datetime.now)

    # 模式内容
    examples: List[str] = field(default_factory=list)  # 实际案例
    keywords: List[str] = field(default_factory=list)  # 关键词

    # 性能指标
    success_count: int = 0  # 成功次数
    total_uses: int = 0  # 总使用次数
    success_rate: float = 0.0  # 成功率
    avg_viral_score: float = 0.0  # 平均爆款分数
    avg_views: float = 0.0  # 平均播放量
    avg_engagement_rate: float = 0.0  # 平均互动率

    # 适用场景
    platforms: List[str] = field(default_factory=list)  # 适用平台
    categories: List[str] = field(default_factory=list)  # 适用分类
    target_audience: Optional[str] = None  # 目标受众

    # Embedding（用于相似度搜索）
    embedding: Optional[np.ndarray] = None

    # 元数据
    source_content_ids: List[str] = field(default_factory=list)  # 来源内容
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 版本控制
    version: int = 1
    parent_pattern_id: Optional[str] = None  # 父模式（如果是演化版本）

    def update_performance(
        self,
        is_success: bool,
        viral_score: float,
        views: int,
        engagement_rate: float
    ):
        """更新性能指标"""
        self.total_uses += 1
        if is_success:
            self.success_count += 1

        # 更新成功率
        self.success_rate = self.success_count / self.total_uses

        # 更新平均指标（增量更新）
        n = self.total_uses
        self.avg_viral_score = (self.avg_viral_score * (n - 1) + viral_score) / n
        self.avg_views = (self.avg_views * (n - 1) + views) / n
        self.avg_engagement_rate = (self.avg_engagement_rate * (n - 1) + engagement_rate) / n

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'pattern_id': self.pattern_id,
            'pattern_type': self.pattern_type,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'template': self.template,
            'examples': self.examples,
            'keywords': self.keywords,
            'performance': {
                'success_count': self.success_count,
                'total_uses': self.total_uses,
                'success_rate': self.success_rate,
                'avg_viral_score': self.avg_viral_score,
                'avg_views': self.avg_views,
                'avg_engagement_rate': self.avg_engagement_rate
            },
            'applicability': {
                'platforms': self.platforms,
                'categories': self.categories,
                'target_audience': self.target_audience
            },
            'source_content_ids': self.source_content_ids,
            'tags': self.tags,
            'metadata': self.metadata,
            'version': self.version,
            'parent_pattern_id': self.parent_pattern_id
        }


class PatternLibrary:
    """
    爆款模式库

    功能：
    1. 存储和管理爆款模式
    2. Embedding 相似度搜索
    3. 性能追踪和排序
    4. 版本控制和演化
    5. 趋势分析
    """

    def __init__(
        self,
        storage_path: Optional[str] = None,
        embed_fn: Optional[Callable[[str], np.ndarray]] = None
    ):
        """
        初始化

        Args:
            storage_path: 持久化存储路径
            embed_fn: Embedding 函数
        """
        self.storage_path = storage_path
        self.embed_fn = embed_fn

        # 模式库
        self.patterns: Dict[str, ViralPattern] = {}

        # 按类型索引
        self.patterns_by_type: Dict[str, List[str]] = defaultdict(list)

        # 按平台索引
        self.patterns_by_platform: Dict[str, List[str]] = defaultdict(list)

        # 按分类索引
        self.patterns_by_category: Dict[str, List[str]] = defaultdict(list)

        # Embedding 索引（用于快速相似度搜索）
        self.embedding_index: Dict[str, np.ndarray] = {}

        # 趋势追踪
        self.trending_patterns: List[Tuple[str, float]] = []  # (pattern_id, trend_score)

        # 加载已有数据
        if storage_path and Path(storage_path).exists():
            self.load_from_file(storage_path)

        logger.info(f"✅ PatternLibrary 初始化完成，已加载 {len(self.patterns)} 个模式")

    def add_pattern(
        self,
        pattern: ViralPattern,
        compute_embedding: bool = True
    ) -> str:
        """
        添加模式

        Args:
            pattern: 爆款模式
            compute_embedding: 是否计算 embedding

        Returns:
            pattern_id
        """
        # 计算 embedding
        if compute_embedding and self.embed_fn and pattern.embedding is None:
            text_for_embedding = f"{pattern.name} {pattern.description} {pattern.template}"
            pattern.embedding = self.embed_fn(text_for_embedding)

        # 存储模式
        self.patterns[pattern.pattern_id] = pattern

        # 更新索引
        self.patterns_by_type[pattern.pattern_type].append(pattern.pattern_id)

        for platform in pattern.platforms:
            self.patterns_by_platform[platform].append(pattern.pattern_id)

        for category in pattern.categories:
            self.patterns_by_category[category].append(pattern.pattern_id)

        # 更新 embedding 索引
        if pattern.embedding is not None:
            self.embedding_index[pattern.pattern_id] = pattern.embedding

        logger.info(f"✅ 添加模式: {pattern.pattern_id} ({pattern.name})")

        return pattern.pattern_id

    def get_pattern(self, pattern_id: str) -> Optional[ViralPattern]:
        """获取模式"""
        return self.patterns.get(pattern_id)

    def search_by_similarity(
        self,
        query_text: str,
        pattern_type: Optional[str] = None,
        platform: Optional[str] = None,
        category: Optional[str] = None,
        top_k: int = 10,
        min_similarity: float = 0.7
    ) -> List[Tuple[ViralPattern, float]]:
        """
        基于相似度搜索模式

        Args:
            query_text: 查询文本
            pattern_type: 模式类型过滤
            platform: 平台过滤
            category: 分类过滤
            top_k: 返回数量
            min_similarity: 最低相似度

        Returns:
            [(pattern, similarity), ...]
        """
        if not self.embed_fn:
            logger.warning("未提供 embed_fn，无法进行相似度搜索")
            return []

        # 计算查询 embedding
        query_embedding = self.embed_fn(query_text)
        if query_embedding is None:
            return []

        # 归一化
        query_embedding = query_embedding / (np.linalg.norm(query_embedding) + 1e-12)

        # 候选模式
        candidate_ids = set(self.patterns.keys())

        # 应用过滤
        if pattern_type:
            candidate_ids &= set(self.patterns_by_type.get(pattern_type, []))
        if platform:
            candidate_ids &= set(self.patterns_by_platform.get(platform, []))
        if category:
            candidate_ids &= set(self.patterns_by_category.get(category, []))

        # 计算相似度
        similarities = []
        for pattern_id in candidate_ids:
            if pattern_id not in self.embedding_index:
                continue

            pattern_embedding = self.embedding_index[pattern_id]
            pattern_embedding = pattern_embedding / (np.linalg.norm(pattern_embedding) + 1e-12)

            similarity = float(np.dot(query_embedding, pattern_embedding))

            if similarity >= min_similarity:
                pattern = self.patterns[pattern_id]
                similarities.append((pattern, similarity))

        # 排序
        similarities.sort(key=lambda x: x[1], reverse=True)

        return similarities[:top_k]

    def search_by_performance(
        self,
        pattern_type: Optional[str] = None,
        platform: Optional[str] = None,
        category: Optional[str] = None,
        min_success_rate: float = 0.0,
        min_uses: int = 0,
        top_k: int = 10,
        sort_by: str = "success_rate"
    ) -> List[ViralPattern]:
        """
        基于性能搜索模式

        Args:
            pattern_type: 模式类型过滤
            platform: 平台过滤
            category: 分类过滤
            min_success_rate: 最低成功率
            min_uses: 最低使用次数
            top_k: 返回数量
            sort_by: 排序字段

        Returns:
            模式列表
        """
        patterns = list(self.patterns.values())

        # 过滤
        if pattern_type:
            patterns = [p for p in patterns if p.pattern_type == pattern_type]
        if platform:
            patterns = [p for p in patterns if platform in p.platforms]
        if category:
            patterns = [p for p in patterns if category in p.categories]
        if min_success_rate > 0:
            patterns = [p for p in patterns if p.success_rate >= min_success_rate]
        if min_uses > 0:
            patterns = [p for p in patterns if p.total_uses >= min_uses]

        # 排序
        if sort_by == "success_rate":
            patterns.sort(key=lambda p: p.success_rate, reverse=True)
        elif sort_by == "avg_viral_score":
            patterns.sort(key=lambda p: p.avg_viral_score, reverse=True)
        elif sort_by == "avg_views":
            patterns.sort(key=lambda p: p.avg_views, reverse=True)
        elif sort_by == "total_uses":
            patterns.sort(key=lambda p: p.total_uses, reverse=True)
        elif sort_by == "created_at":
            patterns.sort(key=lambda p: p.created_at, reverse=True)

        return patterns[:top_k]

    def get_trending_patterns(
        self,
        window_days: int = 7,
        top_k: int = 20
    ) -> List[Tuple[ViralPattern, float]]:
        """
        获取趋势模式

        基于最近使用频率和成功率计算趋势分数

        Args:
            window_days: 时间窗口（天）
            top_k: 返回数量

        Returns:
            [(pattern, trend_score), ...]
        """
        # 简化实现：基于成功率和使用次数
        # 实际应该基于时间窗口内的使用数据

        patterns = list(self.patterns.values())

        # 计算趋势分数
        trend_scores = []
        for pattern in patterns:
            if pattern.total_uses == 0:
                continue

            # 趋势分数 = 成功率 * log(使用次数 + 1)
            trend_score = pattern.success_rate * np.log(pattern.total_uses + 1)
            trend_scores.append((pattern, float(trend_score)))

        # 排序
        trend_scores.sort(key=lambda x: x[1], reverse=True)

        # 更新缓存
        self.trending_patterns = [(p.pattern_id, score) for p, score in trend_scores[:top_k]]

        return trend_scores[:top_k]

    def create_pattern_version(
        self,
        parent_pattern_id: str,
        modifications: Dict[str, Any]
    ) -> Optional[str]:
        """
        创建模式的新版本

        Args:
            parent_pattern_id: 父模式 ID
            modifications: 修改内容

        Returns:
            新模式 ID
        """
        parent = self.patterns.get(parent_pattern_id)
        if not parent:
            logger.warning(f"父模式不存在: {parent_pattern_id}")
            return None

        # 创建新版本
        new_pattern = ViralPattern(
            pattern_id=f"{parent_pattern_id}_v{parent.version + 1}",
            pattern_type=modifications.get('pattern_type', parent.pattern_type),
            name=modifications.get('name', parent.name),
            description=modifications.get('description', parent.description),
            template=modifications.get('template', parent.template),
            examples=modifications.get('examples', parent.examples.copy()),
            keywords=modifications.get('keywords', parent.keywords.copy()),
            platforms=modifications.get('platforms', parent.platforms.copy()),
            categories=modifications.get('categories', parent.categories.copy()),
            target_audience=modifications.get('target_audience', parent.target_audience),
            tags=modifications.get('tags', parent.tags.copy()),
            metadata=modifications.get('metadata', parent.metadata.copy()),
            version=parent.version + 1,
            parent_pattern_id=parent_pattern_id
        )

        # 添加到库
        new_pattern_id = self.add_pattern(new_pattern)

        logger.info(f"✅ 创建模式新版本: {new_pattern_id} (父模式: {parent_pattern_id})")

        return new_pattern_id

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self.patterns:
            return {
                'total_patterns': 0,
                'by_type': {},
                'by_platform': {},
                'by_category': {},
                'avg_success_rate': 0.0,
                'avg_uses': 0.0
            }

        # 按类型统计
        type_stats = defaultdict(int)
        for pattern in self.patterns.values():
            type_stats[pattern.pattern_type] += 1

        # 按平台统计
        platform_stats = defaultdict(int)
        for pattern in self.patterns.values():
            for platform in pattern.platforms:
                platform_stats[platform] += 1

        # 按分类统计
        category_stats = defaultdict(int)
        for pattern in self.patterns.values():
            for category in pattern.categories:
                category_stats[category] += 1

        # 平均指标
        patterns_with_uses = [p for p in self.patterns.values() if p.total_uses > 0]
        if patterns_with_uses:
            avg_success_rate = np.mean([p.success_rate for p in patterns_with_uses])
            avg_uses = np.mean([p.total_uses for p in patterns_with_uses])
        else:
            avg_success_rate = 0.0
            avg_uses = 0.0

        return {
            'total_patterns': len(self.patterns),
            'by_type': dict(type_stats),
            'by_platform': dict(platform_stats),
            'by_category': dict(category_stats),
            'avg_success_rate': float(avg_success_rate),
            'avg_uses': float(avg_uses),
            'patterns_with_uses': len(patterns_with_uses)
        }

    def save_to_file(self, output_path: Optional[str] = None):
        """保存到文件"""
        path = output_path or self.storage_path
        if not path:
            logger.warning("未指定存储路径")
            return

        data = {
            'saved_at': datetime.now().isoformat(),
            'total_patterns': len(self.patterns),
            'patterns': [p.to_dict() for p in self.patterns.values()]
        }

        # 保存 embeddings（单独文件）
        embeddings_data = {
            pattern_id: embedding.tolist()
            for pattern_id, embedding in self.embedding_index.items()
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        embeddings_path = Path(path).with_suffix('.embeddings.json')
        with open(embeddings_path, 'w', encoding='utf-8') as f:
            json.dump(embeddings_data, f, indent=2)

        logger.info(f"✅ 已保存 {len(self.patterns)} 个模式到 {path}")

    def load_from_file(self, input_path: str):
        """从文件加载"""
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 加载模式
        for pattern_dict in data.get('patterns', []):
            pattern = ViralPattern(
                pattern_id=pattern_dict['pattern_id'],
                pattern_type=pattern_dict['pattern_type'],
                name=pattern_dict['name'],
                description=pattern_dict['description'],
                created_at=datetime.fromisoformat(pattern_dict['created_at']),
                template=pattern_dict['template'],
                examples=pattern_dict['examples'],
                keywords=pattern_dict['keywords'],
                success_count=pattern_dict['performance']['success_count'],
                total_uses=pattern_dict['performance']['total_uses'],
                success_rate=pattern_dict['performance']['success_rate'],
                avg_viral_score=pattern_dict['performance']['avg_viral_score'],
                avg_views=pattern_dict['performance']['avg_views'],
                avg_engagement_rate=pattern_dict['performance']['avg_engagement_rate'],
                platforms=pattern_dict['applicability']['platforms'],
                categories=pattern_dict['applicability']['categories'],
                target_audience=pattern_dict['applicability'].get('target_audience'),
                source_content_ids=pattern_dict['source_content_ids'],
                tags=pattern_dict['tags'],
                metadata=pattern_dict['metadata'],
                version=pattern_dict['version'],
                parent_pattern_id=pattern_dict.get('parent_pattern_id')
            )

            self.add_pattern(pattern, compute_embedding=False)

        # 加载 embeddings
        embeddings_path = Path(input_path).with_suffix('.embeddings.json')
        if embeddings_path.exists():
            with open(embeddings_path, 'r', encoding='utf-8') as f:
                embeddings_data = json.load(f)

            for pattern_id, embedding_list in embeddings_data.items():
                if pattern_id in self.patterns:
                    embedding = np.array(embedding_list, dtype=np.float32)
                    self.patterns[pattern_id].embedding = embedding
                    self.embedding_index[pattern_id] = embedding

        logger.info(f"✅ 已加载 {len(self.patterns)} 个模式从 {input_path}")
