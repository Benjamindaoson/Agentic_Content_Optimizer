"""
成功要素提取器

从爆款笔记中提取可复用的模式
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import numpy as np
from collections import defaultdict, Counter

from app.db import XHSNote, XHSMetrics, XHSAnalysis, Pattern, PatternSample
from app.analyzers.viral_analyzer import ComprehensiveAnalysis

logger = logging.getLogger(__name__)


@dataclass
class ExtractedPattern:
    """提取的模式"""
    pattern_id: str
    category: str
    name: str
    description: str

    # 模式内容
    hook_template: str
    body_structure: Dict[str, Any]
    cta_template: str

    # 关键特征
    keywords: List[str]
    emotion_curve: List[Tuple[int, float]]

    # 视觉特征
    cover_layout: str
    dominant_color: str
    visual_elements: Dict[str, Any]

    # 性能指标
    sample_note_ids: List[str]
    avg_viral_score: float
    avg_views: float
    avg_engagement_rate: float

    # 适用场景
    platforms: List[str]
    target_audience: str


class SuccessFactorExtractor:
    """
    成功要素提取器

    从爆款集合中提取共同模式
    """

    def __init__(self, embed_fn: Optional[Any] = None):
        """
        初始化提取器

        Args:
            embed_fn: Embedding 函数（用于聚类）
        """
        self.embed_fn = embed_fn
        logger.info("✅ SuccessFactorExtractor 初始化完成")

    async def extract_patterns(
        self,
        notes: List[XHSNote],
        analyses: List[ComprehensiveAnalysis],
        category: str,
        min_cluster_size: int = 5
    ) -> List[ExtractedPattern]:
        """
        从爆款集合中提取模式

        Args:
            notes: 爆款笔记列表
            analyses: 分析结果列表
            category: 分类
            min_cluster_size: 最小聚类大小

        Returns:
            提取的模式列表
        """
        logger.info(f"开始提取模式：分类={category}, 笔记数={len(notes)}")

        if len(notes) < min_cluster_size:
            logger.warning(f"笔记数量不足，无法提取模式: {len(notes)} < {min_cluster_size}")
            return []

        # 1. 聚类（基于 embedding + 指标特征）
        clusters = await self._cluster_notes(notes, analyses, min_cluster_size)

        logger.info(f"聚类完成：{len(clusters)} 个簇")

        # 2. 从每个簇中提取模式
        patterns = []
        for cluster_id, cluster_notes in enumerate(clusters):
            try:
                pattern = await self._extract_pattern_from_cluster(
                    cluster_notes,
                    analyses,
                    category,
                    cluster_id
                )
                patterns.append(pattern)
            except Exception as e:
                logger.error(f"从簇 {cluster_id} 提取模式失败: {e}")
                continue

        # 3. 提取边界模式（极端但有效）
        boundary_patterns = await self._extract_boundary_patterns(
            notes,
            analyses,
            category
        )
        patterns.extend(boundary_patterns)

        logger.info(f"✅ 模式提取完成：{len(patterns)} 个模式")
        return patterns

    async def _cluster_notes(
        self,
        notes: List[XHSNote],
        analyses: List[ComprehensiveAnalysis],
        min_cluster_size: int
    ) -> List[List[XHSNote]]:
        """
        聚类笔记

        基于 embedding + 指标特征
        """
        # TODO: 实际使用 embedding 聚类
        # 这里是简化实现：基于结构类型聚类

        clusters = defaultdict(list)

        for note, analysis in zip(notes, analyses):
            # 使用结构类型作为聚类键
            cluster_key = (
                analysis.structure.hook_type,
                analysis.structure.body_structure,
                analysis.structure.cta_type
            )
            clusters[cluster_key].append(note)

        # 过滤小簇
        filtered_clusters = [
            cluster for cluster in clusters.values()
            if len(cluster) >= min_cluster_size
        ]

        return filtered_clusters

    async def _extract_pattern_from_cluster(
        self,
        cluster_notes: List[XHSNote],
        all_analyses: List[ComprehensiveAnalysis],
        category: str,
        cluster_id: int
    ) -> ExtractedPattern:
        """从簇中提取模式"""

        # 获取簇内笔记的分析结果
        note_ids = {note.note_id for note in cluster_notes}
        cluster_analyses = [
            analysis for analysis in all_analyses
            if analysis.note_id in note_ids
        ]

        # 1. 提取 Hook 模板
        hook_template = self._extract_hook_template(cluster_analyses)

        # 2. 提取 Body 结构
        body_structure = self._extract_body_structure(cluster_analyses)

        # 3. 提取 CTA 模板
        cta_template = self._extract_cta_template(cluster_analyses)

        # 4. 提取关键词
        keywords = self._extract_common_keywords(cluster_analyses)

        # 5. 提取情绪曲线
        emotion_curve = self._extract_emotion_curve(cluster_analyses)

        # 6. 提取视觉特征
        cover_layout, dominant_color, visual_elements = self._extract_visual_features(cluster_analyses)

        # 7. 计算性能指标
        avg_viral_score, avg_views, avg_engagement_rate = self._calculate_cluster_metrics(cluster_notes)

        # 8. 推断目标受众
        target_audience = self._infer_target_audience(cluster_analyses)

        # 9. 生成模式名称和描述
        name = self._generate_pattern_name(hook_template, body_structure, cta_template)
        description = self._generate_pattern_description(
            hook_template, body_structure, cta_template, keywords
        )

        pattern_id = f"pattern_{category}_{cluster_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        return ExtractedPattern(
            pattern_id=pattern_id,
            category=category,
            name=name,
            description=description,
            hook_template=hook_template,
            body_structure=body_structure,
            cta_template=cta_template,
            keywords=keywords,
            emotion_curve=emotion_curve,
            cover_layout=cover_layout,
            dominant_color=dominant_color,
            visual_elements=visual_elements,
            sample_note_ids=[note.note_id for note in cluster_notes],
            avg_viral_score=avg_viral_score,
            avg_views=avg_views,
            avg_engagement_rate=avg_engagement_rate,
            platforms=["xiaohongshu"],
            target_audience=target_audience
        )

    def _extract_hook_template(self, analyses: List[ComprehensiveAnalysis]) -> str:
        """提取 Hook 模板"""
        # 统计最常见的 Hook 类型
        hook_types = [a.structure.hook_type for a in analyses]
        most_common_type = Counter(hook_types).most_common(1)[0][0]

        # 提取该类型的典型 Hook
        hooks = [
            a.structure.hook_text for a in analyses
            if a.structure.hook_type == most_common_type
        ]

        # 简化：返回第一个作为模板
        if hooks:
            return self._generalize_template(hooks[0])
        else:
            return "{Hook}"

    def _generalize_template(self, text: str) -> str:
        """泛化模板（替换具体内容为占位符）"""
        # 简化实现：保留结构，替换具体词汇
        import re

        # 替换数字
        text = re.sub(r'\d+', '{数字}', text)

        # 替换品牌名（简化）
        brands = ["雅诗兰黛", "兰蔻", "SK-II", "资生堂"]
        for brand in brands:
            text = text.replace(brand, '{品牌}')

        return text

    def _extract_body_structure(self, analyses: List[ComprehensiveAnalysis]) -> Dict[str, Any]:
        """提取 Body 结构"""
        # 统计最常见的 Body 结构
        body_structures = [a.structure.body_structure for a in analyses]
        most_common_structure = Counter(body_structures).most_common(1)[0][0]

        # 统计平均段落数
        avg_sections = np.mean([len(a.structure.body_sections) for a in analyses])

        return {
            'type': most_common_structure,
            'avg_sections': int(avg_sections),
            'rhythm': Counter([a.structure.rhythm for a in analyses]).most_common(1)[0][0]
        }

    def _extract_cta_template(self, analyses: List[ComprehensiveAnalysis]) -> str:
        """提取 CTA 模板"""
        # 统计最常见的 CTA 类型
        cta_types = [a.structure.cta_type for a in analyses]
        most_common_type = Counter(cta_types).most_common(1)[0][0]

        # 提取该类型的典型 CTA
        ctas = [
            a.structure.cta_text for a in analyses
            if a.structure.cta_type == most_common_type
        ]

        # 简化：返回第一个作为模板
        if ctas:
            return self._generalize_template(ctas[0])
        else:
            return "{CTA}"

    def _extract_common_keywords(self, analyses: List[ComprehensiveAnalysis]) -> List[str]:
        """提取共同关键词"""
        all_keywords = []
        for analysis in analyses:
            all_keywords.extend([kw for kw, _ in analysis.topics.keywords])

        # 统计词频
        keyword_counts = Counter(all_keywords)

        # 返回 Top-10
        return [kw for kw, _ in keyword_counts.most_common(10)]

    def _extract_emotion_curve(self, analyses: List[ComprehensiveAnalysis]) -> List[Tuple[int, float]]:
        """提取情绪曲线（平均）"""
        if not analyses:
            return []

        # 收集所有情绪曲线
        curves = [a.emotion.emotion_curve for a in analyses]

        # 计算平均曲线
        max_len = max(len(curve) for curve in curves)
        avg_curve = []

        for i in range(max_len):
            values = [curve[i][1] for curve in curves if i < len(curve)]
            if values:
                avg_curve.append((i * 20, float(np.mean(values))))

        return avg_curve

    def _extract_visual_features(
        self,
        analyses: List[ComprehensiveAnalysis]
    ) -> Tuple[str, str, Dict[str, Any]]:
        """提取视觉特征"""
        # 统计最常见的布局
        layouts = [a.visual.layout for a in analyses]
        most_common_layout = Counter(layouts).most_common(1)[0][0]

        # 统计最常见的主色调
        all_colors = []
        for analysis in analyses:
            all_colors.extend(analysis.visual.dominant_colors)

        most_common_color = Counter(all_colors).most_common(1)[0][0] if all_colors else "#FFFFFF"

        # 统计视觉风格
        styles = [a.visual.visual_style for a in analyses]
        most_common_style = Counter(styles).most_common(1)[0][0]

        visual_elements = {
            'style': most_common_style,
            'color_scheme': Counter([a.visual.color_scheme for a in analyses]).most_common(1)[0][0]
        }

        return most_common_layout, most_common_color, visual_elements

    def _calculate_cluster_metrics(
        self,
        cluster_notes: List[XHSNote]
    ) -> Tuple[float, float, float]:
        """计算簇的性能指标"""
        viral_scores = [note.metrics.viral_score for note in cluster_notes if note.metrics]
        views = [note.metrics.views for note in cluster_notes if note.metrics]
        engagement_rates = [note.metrics.engagement_rate for note in cluster_notes if note.metrics]

        avg_viral_score = float(np.mean(viral_scores)) if viral_scores else 0.0
        avg_views = float(np.mean(views)) if views else 0.0
        avg_engagement_rate = float(np.mean(engagement_rates)) if engagement_rates else 0.0

        return avg_viral_score, avg_views, avg_engagement_rate

    def _infer_target_audience(self, analyses: List[ComprehensiveAnalysis]) -> str:
        """推断目标受众"""
        # 统计年龄段
        age_ranges = [a.audience.target_age_range for a in analyses]
        avg_min_age = int(np.mean([r[0] for r in age_ranges]))
        avg_max_age = int(np.mean([r[1] for r in age_ranges]))

        # 统计性别
        genders = [a.audience.target_gender for a in analyses]
        most_common_gender = Counter(genders).most_common(1)[0][0]

        return f"{avg_min_age}-{avg_max_age}岁 {most_common_gender}"

    def _generate_pattern_name(
        self,
        hook_template: str,
        body_structure: Dict[str, Any],
        cta_template: str
    ) -> str:
        """生成模式名称"""
        # 简化：基于结构类型
        return f"{body_structure['type']}_{body_structure['rhythm']}_模式"

    def _generate_pattern_description(
        self,
        hook_template: str,
        body_structure: Dict[str, Any],
        cta_template: str,
        keywords: List[str]
    ) -> str:
        """生成模式描述"""
        return (
            f"使用 {body_structure['type']} 结构，"
            f"节奏为 {body_structure['rhythm']}，"
            f"关键词包括：{', '.join(keywords[:5])}"
        )

    async def _extract_boundary_patterns(
        self,
        notes: List[XHSNote],
        analyses: List[ComprehensiveAnalysis],
        category: str
    ) -> List[ExtractedPattern]:
        """提取边界模式（极端但有效）"""
        boundary_patterns = []

        # 1. 找出极高互动率的笔记
        high_engagement_notes = sorted(
            [(note, analysis) for note, analysis in zip(notes, analyses) if note.metrics],
            key=lambda x: x[0].metrics.engagement_rate,
            reverse=True
        )[:3]

        # 2. 为每个极端笔记创建单独的模式
        for i, (note, analysis) in enumerate(high_engagement_notes):
            pattern_id = f"pattern_{category}_boundary_{i}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            pattern = ExtractedPattern(
                pattern_id=pattern_id,
                category=category,
                name=f"高互动边界模式_{i+1}",
                description=f"极高互动率模式（{note.metrics.engagement_rate:.2%}）",
                hook_template=analysis.structure.hook_text,
                body_structure={'type': analysis.structure.body_structure, 'sections': len(analysis.structure.body_sections)},
                cta_template=analysis.structure.cta_text,
                keywords=[kw for kw, _ in analysis.topics.keywords[:10]],
                emotion_curve=analysis.emotion.emotion_curve,
                cover_layout=analysis.visual.layout,
                dominant_color=analysis.visual.dominant_colors[0] if analysis.visual.dominant_colors else "#FFFFFF",
                visual_elements={'style': analysis.visual.visual_style},
                sample_note_ids=[note.note_id],
                avg_viral_score=note.metrics.viral_score,
                avg_views=float(note.metrics.views),
                avg_engagement_rate=note.metrics.engagement_rate,
                platforms=["xiaohongshu"],
                target_audience=f"{analysis.audience.target_age_range[0]}-{analysis.audience.target_age_range[1]}岁"
            )

            boundary_patterns.append(pattern)

        logger.info(f"✅ 提取边界模式：{len(boundary_patterns)} 个")
        return boundary_patterns
