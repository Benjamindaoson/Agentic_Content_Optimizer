"""
封面建议系统

基于视觉分析和模式库的封面推荐
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from collections import Counter
import numpy as np
from sqlalchemy.orm import Session

from app.db import Pattern, XHSCover


@dataclass
class CoverSuggestion:
    """封面建议"""
    layout: str  # left_text_right_image, top_image_bottom_text, center_text, full_image
    dominant_color: str  # HEX 颜色
    color_scheme: str  # warm, cool, neutral, vibrant
    visual_style: str  # minimalist, rich, professional, casual

    # 文字建议
    title_position: str  # top_left, top_center, center, bottom_left, bottom_center
    title_keywords: List[str]  # 建议在封面上显示的关键词
    font_style: str  # bold, elegant, playful, modern

    # 对象建议
    suggested_objects: List[str]  # 建议包含的对象
    avoid_objects: List[str]  # 建议避免的对象

    # 置信度
    confidence: float
    reasoning: str  # 推荐理由


class CoverSuggester:
    """
    封面建议系统

    核心功能：
    1. 基于分类和话题分析历史爆款封面
    2. 提取视觉模式（布局、色彩、对象）
    3. 生成封面建议
    4. 提供关键词和文字位置建议
    """

    def __init__(self):
        pass

    async def suggest_cover(
        self,
        category: str,
        topic: str,
        keywords: List[str],
        target_audience: Optional[str] = None,
        db: Session = None
    ) -> CoverSuggestion:
        """
        生成封面建议

        Args:
            category: 分类（美妆/穿搭/美食等）
            topic: 话题
            keywords: 关键词
            target_audience: 目标受众
            db: 数据库会话

        Returns:
            封面建议
        """
        # 1. 分析历史爆款封面
        visual_patterns = await self._analyze_viral_covers(
            category=category,
            db=db
        )

        # 2. 基于话题和关键词调整
        adjusted_patterns = await self._adjust_for_topic(
            patterns=visual_patterns,
            topic=topic,
            keywords=keywords
        )

        # 3. 基于目标受众调整
        if target_audience:
            adjusted_patterns = await self._adjust_for_audience(
                patterns=adjusted_patterns,
                audience=target_audience
            )

        # 4. 生成建议
        suggestion = await self._generate_suggestion(
            patterns=adjusted_patterns,
            keywords=keywords
        )

        return suggestion

    async def suggest_multiple_covers(
        self,
        category: str,
        topic: str,
        keywords: List[str],
        num_suggestions: int = 3,
        db: Session = None
    ) -> List[CoverSuggestion]:
        """
        生成多个封面建议（提供多样性）

        Args:
            category: 分类
            topic: 话题
            keywords: 关键词
            num_suggestions: 建议数量
            db: 数据库会话

        Returns:
            封面建议列表
        """
        suggestions = []

        # 分析历史爆款封面
        visual_patterns = await self._analyze_viral_covers(
            category=category,
            db=db
        )

        # 生成多个不同风格的建议
        styles = ['minimalist', 'rich', 'professional', 'casual']

        for i in range(num_suggestions):
            style = styles[i % len(styles)]

            # 过滤特定风格的模式
            style_patterns = [
                p for p in visual_patterns
                if p.get('visual_style') == style
            ]

            if not style_patterns:
                style_patterns = visual_patterns

            # 生成建议
            suggestion = await self._generate_suggestion(
                patterns=style_patterns,
                keywords=keywords,
                preferred_style=style
            )

            suggestions.append(suggestion)

        return suggestions

    async def _analyze_viral_covers(
        self,
        category: str,
        db: Session,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """分析历史爆款封面"""
        if not db:
            # 返回默认模式
            return self._get_default_patterns(category)

        # 查询爆款笔记的封面
        from app.db import XHSNote

        viral_notes = db.query(XHSNote).filter(
            XHSNote.category == category,
            XHSNote.is_viral == True
        ).limit(limit).all()

        # 提取视觉特征
        patterns = []
        for note in viral_notes:
            if note.cover:
                pattern = {
                    'layout': note.cover.layout,
                    'dominant_color': note.cover.dominant_color,
                    'color_scheme': note.cover.color_scheme,
                    'visual_style': note.cover.visual_style,
                    'objects': note.cover.objects or [],
                    'text_regions': note.cover.text_regions or [],
                    'viral_score': note.metrics.viral_score if note.metrics else 0.0
                }
                patterns.append(pattern)

        return patterns

    def _get_default_patterns(self, category: str) -> List[Dict[str, Any]]:
        """获取默认模式（当数据库无数据时）"""
        # 基于分类的默认模式
        defaults = {
            '美妆': [
                {
                    'layout': 'left_text_right_image',
                    'dominant_color': '#FFB6C1',
                    'color_scheme': 'warm',
                    'visual_style': 'elegant',
                    'objects': ['face', 'cosmetics'],
                    'text_regions': [{'position': 'top_left'}],
                    'viral_score': 0.8
                },
                {
                    'layout': 'top_image_bottom_text',
                    'dominant_color': '#FFC0CB',
                    'color_scheme': 'vibrant',
                    'visual_style': 'rich',
                    'objects': ['cosmetics', 'hand'],
                    'text_regions': [{'position': 'bottom_center'}],
                    'viral_score': 0.75
                }
            ],
            '穿搭': [
                {
                    'layout': 'full_image',
                    'dominant_color': '#F5F5DC',
                    'color_scheme': 'neutral',
                    'visual_style': 'minimalist',
                    'objects': ['person', 'clothing'],
                    'text_regions': [{'position': 'top_center'}],
                    'viral_score': 0.85
                }
            ],
            '美食': [
                {
                    'layout': 'center_text',
                    'dominant_color': '#FFA500',
                    'color_scheme': 'warm',
                    'visual_style': 'rich',
                    'objects': ['food', 'plate'],
                    'text_regions': [{'position': 'center'}],
                    'viral_score': 0.8
                }
            ]
        }

        return defaults.get(category, defaults['美妆'])

    async def _adjust_for_topic(
        self,
        patterns: List[Dict[str, Any]],
        topic: str,
        keywords: List[str]
    ) -> List[Dict[str, Any]]:
        """基于话题调整模式"""
        # 根据话题关键词调整色彩和风格
        topic_lower = topic.lower()

        # 色彩调整
        if any(word in topic_lower for word in ['冬季', '冷', '雪']):
            # 冷色调
            for pattern in patterns:
                if pattern['color_scheme'] == 'warm':
                    pattern['color_scheme'] = 'cool'
                    pattern['dominant_color'] = '#87CEEB'  # 天蓝色

        elif any(word in topic_lower for word in ['夏季', '热', '阳光']):
            # 暖色调
            for pattern in patterns:
                if pattern['color_scheme'] == 'cool':
                    pattern['color_scheme'] = 'warm'
                    pattern['dominant_color'] = '#FFA500'  # 橙色

        # 风格调整
        if any(word in topic_lower for word in ['专业', '职场', '正式']):
            for pattern in patterns:
                pattern['visual_style'] = 'professional'

        elif any(word in topic_lower for word in ['可爱', '少女', '甜美']):
            for pattern in patterns:
                pattern['visual_style'] = 'playful'

        return patterns

    async def _adjust_for_audience(
        self,
        patterns: List[Dict[str, Any]],
        audience: str
    ) -> List[Dict[str, Any]]:
        """基于目标受众调整模式"""
        audience_lower = audience.lower()

        # 年龄段调整
        if '18-25' in audience_lower or 'z世代' in audience_lower:
            # 年轻受众：鲜艳、活泼
            for pattern in patterns:
                pattern['color_scheme'] = 'vibrant'
                pattern['visual_style'] = 'playful'

        elif '30-40' in audience_lower or '职场' in audience_lower:
            # 成熟受众：专业、简约
            for pattern in patterns:
                pattern['color_scheme'] = 'neutral'
                pattern['visual_style'] = 'professional'

        return patterns

    async def _generate_suggestion(
        self,
        patterns: List[Dict[str, Any]],
        keywords: List[str],
        preferred_style: Optional[str] = None
    ) -> CoverSuggestion:
        """生成封面建议"""
        if not patterns:
            # 返回默认建议
            return self._get_default_suggestion(keywords)

        # 统计最常见的特征
        layouts = [p['layout'] for p in patterns]
        colors = [p['dominant_color'] for p in patterns]
        color_schemes = [p['color_scheme'] for p in patterns]
        visual_styles = [p['visual_style'] for p in patterns]

        # 加权选择（基于 viral_score）
        weights = [p.get('viral_score', 0.5) for p in patterns]
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]

        # 选择最佳布局
        layout_counter = Counter(layouts)
        best_layout = layout_counter.most_common(1)[0][0]

        # 选择最佳色彩
        color_counter = Counter(colors)
        best_color = color_counter.most_common(1)[0][0]

        # 选择最佳配色方案
        scheme_counter = Counter(color_schemes)
        best_scheme = scheme_counter.most_common(1)[0][0]

        # 选择最佳风格
        if preferred_style:
            best_style = preferred_style
        else:
            style_counter = Counter(visual_styles)
            best_style = style_counter.most_common(1)[0][0]

        # 提取常见对象
        all_objects = []
        for p in patterns:
            all_objects.extend(p.get('objects', []))
        object_counter = Counter(all_objects)
        suggested_objects = [obj for obj, _ in object_counter.most_common(3)]

        # 确定标题位置
        title_position = self._determine_title_position(best_layout)

        # 选择关键词（最多3个）
        title_keywords = keywords[:3] if len(keywords) >= 3 else keywords

        # 确定字体风格
        font_style = self._determine_font_style(best_style)

        # 计算置信度
        confidence = min(len(patterns) / 50.0, 1.0)  # 样本越多，置信度越高

        # 分析失败案例，找出应该避免的元素
        avoid_objects = self._analyze_failed_cases(category, patterns)

        # 生成推荐理由
        reasoning = f"基于 {len(patterns)} 个爆款封面分析，{best_layout} 布局在该分类中表现最佳，{best_scheme} 配色方案更受欢迎。"
        if avoid_objects:
            reasoning += f" 建议避免使用：{', '.join(avoid_objects[:3])}。"

        return CoverSuggestion(
            layout=best_layout,
            dominant_color=best_color,
            color_scheme=best_scheme,
            visual_style=best_style,
            title_position=title_position,
            title_keywords=title_keywords,
            font_style=font_style,
            suggested_objects=suggested_objects,
            avoid_objects=avoid_objects,
            confidence=confidence,
            reasoning=reasoning
        )

    def _determine_title_position(self, layout: str) -> str:
        """确定标题位置"""
        position_map = {
            'left_text_right_image': 'top_left',
            'top_image_bottom_text': 'bottom_center',
            'center_text': 'center',
            'full_image': 'top_center'
        }
        return position_map.get(layout, 'top_center')

    def _determine_font_style(self, visual_style: str) -> str:
        """确定字体风格"""
        font_map = {
            'minimalist': 'modern',
            'rich': 'bold',
            'professional': 'elegant',
            'casual': 'playful'
        }
        return font_map.get(visual_style, 'modern')

    def _analyze_failed_cases(
        self,
        category: str,
        patterns: List[Dict[str, Any]]
    ) -> List[str]:
        """
        分析失败案例，找出应该避免的元素

        Args:
            category: 分类
            patterns: 爆款模式列表

        Returns:
            应该避免的对象列表
        """
        avoid_objects = []

        try:
            # 1. 从历史数据中找出低表现的封面特征
            # 这里使用简化的启发式规则
            low_performance_indicators = {
                '美妆': ['messy_background', 'dark_lighting', 'cluttered_text'],
                '穿搭': ['poor_lighting', 'busy_pattern', 'unclear_outfit'],
                '美食': ['unappetizing_color', 'messy_presentation', 'dark_photo'],
                '旅行': ['blurry_image', 'crowded_scene', 'poor_weather'],
                '健身': ['unclear_pose', 'messy_gym', 'poor_lighting']
            }

            # 2. 获取该分类的常见失败元素
            category_avoid = low_performance_indicators.get(category, [])
            avoid_objects.extend(category_avoid)

            # 3. 分析爆款模式，找出从未出现的元素（可能是负面的）
            # 统计所有成功案例中的对象
            successful_objects = set()
            for pattern in patterns:
                objects = pattern.get('visual_elements', {}).get('objects', [])
                successful_objects.update(objects)

            # 4. 通用的应该避免的元素
            universal_avoid = [
                'watermark',  # 水印
                'low_quality',  # 低质量
                'text_heavy',  # 文字过多
                'too_dark',  # 过暗
                'too_bright',  # 过亮
                'blurry'  # 模糊
            ]

            # 5. 合并并去重
            avoid_objects.extend(universal_avoid)
            avoid_objects = list(set(avoid_objects))

            # 6. 限制返回数量
            return avoid_objects[:5]

        except Exception as e:
            logger.warning(f"Failed to analyze failed cases: {e}")
            return ['low_quality', 'blurry', 'text_heavy']

    def _get_default_suggestion(self, keywords: List[str]) -> CoverSuggestion:
        """获取默认建议"""
        return CoverSuggestion(
            layout='left_text_right_image',
            dominant_color='#FFB6C1',
            color_scheme='warm',
            visual_style='minimalist',
            title_position='top_left',
            title_keywords=keywords[:3],
            font_style='modern',
            suggested_objects=['person', 'product'],
            avoid_objects=[],
            confidence=0.5,
            reasoning="默认建议（数据不足）"
        )
