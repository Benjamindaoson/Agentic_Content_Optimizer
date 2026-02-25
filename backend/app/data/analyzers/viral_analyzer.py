"""
爆款内容分析器

多维度分析爆款笔记：结构、情感、话题、视觉、时机、受众
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json

logger = logging.getLogger(__name__)


@dataclass
class StructureAnalysis:
    """结构分析结果"""
    hook_type: str  # 开场类型：question/urgency/story/data/controversy
    hook_text: str  # Hook 文本
    hook_score: float  # Hook 质量分数

    body_structure: str  # Body 结构：problem_solution/before_after/list/story
    body_sections: List[Dict[str, str]]  # Body 分段
    body_score: float  # Body 质量分数

    cta_type: str  # CTA 类型：direct/soft/question/urgency
    cta_text: str  # CTA 文本
    cta_score: float  # CTA 质量分数

    rhythm: str  # 节奏：fast/medium/slow
    transitions: List[str]  # 转折点
    overall_score: float  # 整体结构分数


@dataclass
class EmotionAnalysis:
    """情感分析结果"""
    primary_emotion: str  # 主情绪：joy/surprise/fear/anger/sadness/trust
    emotion_intensity: float  # 情绪强度（0-1）
    emotion_curve: List[Tuple[int, float]]  # 情绪曲线（位置, 强度）
    trigger_words: List[str]  # 触发词
    sentiment_score: float  # 情感分数（-1 到 1）


@dataclass
class TopicAnalysis:
    """话题分析结果"""
    core_topics: List[str]  # 核心话题
    hot_topics: List[str]  # 热点话题
    controversy_level: float  # 争议度（0-1）
    pain_points: List[str]  # 痛点
    keywords: List[Tuple[str, float]]  # 关键词及权重


@dataclass
class VisualAnalysis:
    """视觉分析结果"""
    layout: str  # 布局：left_text_right_image/top_image_bottom_text/center_text/full_image
    dominant_colors: List[str]  # 主色调（HEX）
    color_scheme: str  # 配色方案：warm/cool/neutral/vibrant
    objects: List[Dict[str, Any]]  # 检测到的对象
    text_regions: List[Dict[str, Any]]  # 文字区域
    visual_style: str  # 视觉风格：minimalist/rich/professional/casual
    visual_score: float  # 视觉质量分数


@dataclass
class TimingAnalysis:
    """时机分析结果"""
    publish_hour: int  # 发布小时
    publish_day_of_week: int  # 发布星期几（0=周一）
    time_category: str  # 时间类别：morning/noon/afternoon/evening/night
    velocity_24h: float  # 24小时速度
    peak_time: Optional[datetime]  # 峰值时间
    timing_score: float  # 时机分数


@dataclass
class AudienceAnalysis:
    """受众分析结果"""
    target_age_range: Tuple[int, int]  # 目标年龄段
    target_gender: str  # 目标性别：male/female/all
    interests: List[str]  # 兴趣标签
    pain_points: List[str]  # 痛点
    aspirations: List[str]  # 愿望
    audience_match_score: float  # 受众匹配分数


@dataclass
class ComprehensiveAnalysis:
    """综合分析结果"""
    note_id: str
    structure: StructureAnalysis
    emotion: EmotionAnalysis
    topics: TopicAnalysis
    visual: VisualAnalysis
    timing: TimingAnalysis
    audience: AudienceAnalysis
    overall_score: float  # 综合分数
    analyzed_at: datetime = field(default_factory=datetime.now)


class ViralAnalyzer:
    """
    爆款内容分析器

    使用 LLM 进行多维度分析
    """

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        vision_model: Optional[Any] = None
    ):
        """
        初始化分析器

        Args:
            llm_client: LLM 客户端（用于文本分析）
            vision_model: 视觉模型（用于封面分析）
        """
        self.llm_client = llm_client
        self.vision_model = vision_model
        logger.info("✅ ViralAnalyzer 初始化完成")

    async def analyze(
        self,
        note_id: str,
        title: str,
        text: str,
        cover_path: Optional[str] = None,
        metrics: Optional[Dict[str, int]] = None,
        publish_time: Optional[datetime] = None
    ) -> ComprehensiveAnalysis:
        """
        综合分析笔记

        Args:
            note_id: 笔记ID
            title: 标题
            text: 正文
            cover_path: 封面路径
            metrics: 指标数据
            publish_time: 发布时间

        Returns:
            综合分析结果
        """
        logger.info(f"开始分析笔记: {note_id}")

        # 1. 结构分析
        structure = await self._analyze_structure(title, text)

        # 2. 情感分析
        emotion = await self._analyze_emotion(text)

        # 3. 话题分析
        topics = await self._analyze_topics(title, text)

        # 4. 视觉分析
        visual = await self._analyze_visual(cover_path) if cover_path else self._default_visual()

        # 5. 时机分析
        timing = await self._analyze_timing(publish_time, metrics)

        # 6. 受众分析
        audience = await self._analyze_audience(title, text, topics)

        # 7. 计算综合分数
        overall_score = self._calculate_overall_score(
            structure, emotion, topics, visual, timing, audience
        )

        result = ComprehensiveAnalysis(
            note_id=note_id,
            structure=structure,
            emotion=emotion,
            topics=topics,
            visual=visual,
            timing=timing,
            audience=audience,
            overall_score=overall_score
        )

        logger.info(f"✅ 分析完成: {note_id}, 综合分数: {overall_score:.3f}")
        return result

    async def _analyze_structure(self, title: str, text: str) -> StructureAnalysis:
        """结构分析"""
        # TODO: 实际使用 LLM 分析
        # 这里是简化实现

        # 检测 Hook 类型
        hook_type = self._detect_hook_type(title)
        hook_text = title
        hook_score = 0.8

        # 检测 Body 结构
        body_structure = self._detect_body_structure(text)
        body_sections = self._split_body_sections(text)
        body_score = 0.75

        # 检测 CTA 类型
        cta_type, cta_text = self._detect_cta(text)
        cta_score = 0.7

        # 检测节奏
        rhythm = self._detect_rhythm(text)

        # 检测转折点
        transitions = self._detect_transitions(text)

        # 计算整体分数
        overall_score = (hook_score + body_score + cta_score) / 3

        return StructureAnalysis(
            hook_type=hook_type,
            hook_text=hook_text,
            hook_score=hook_score,
            body_structure=body_structure,
            body_sections=body_sections,
            body_score=body_score,
            cta_type=cta_type,
            cta_text=cta_text,
            cta_score=cta_score,
            rhythm=rhythm,
            transitions=transitions,
            overall_score=overall_score
        )

    def _detect_hook_type(self, title: str) -> str:
        """检测 Hook 类型"""
        if "?" in title or "吗" in title or "如何" in title:
            return "question"
        elif "限时" in title or "立即" in title or "马上" in title:
            return "urgency"
        elif any(word in title for word in ["故事", "经历", "我的"]):
            return "story"
        elif any(char.isdigit() for char in title):
            return "data"
        elif any(word in title for word in ["真相", "揭秘", "不要"]):
            return "controversy"
        else:
            return "statement"

    def _detect_body_structure(self, text: str) -> str:
        """检测 Body 结构"""
        if "问题" in text and "解决" in text:
            return "problem_solution"
        elif "之前" in text and "之后" in text:
            return "before_after"
        elif text.count("\n") > 3 or any(str(i) in text for i in range(1, 6)):
            return "list"
        else:
            return "story"

    def _split_body_sections(self, text: str) -> List[Dict[str, str]]:
        """分割 Body 段落"""
        sections = []
        paragraphs = text.split("\n\n")

        for i, para in enumerate(paragraphs[:5]):  # 最多5段
            if para.strip():
                sections.append({
                    "index": i,
                    "text": para.strip()[:100],  # 截取前100字
                    "type": "paragraph"
                })

        return sections

    def _detect_cta(self, text: str) -> Tuple[str, str]:
        """检测 CTA 类型"""
        last_sentence = text.split("。")[-1].strip()

        if any(word in last_sentence for word in ["立即", "马上", "现在", "快来"]):
            return "direct", last_sentence
        elif "?" in last_sentence or "吗" in last_sentence:
            return "question", last_sentence
        elif any(word in last_sentence for word in ["限时", "仅剩", "最后"]):
            return "urgency", last_sentence
        else:
            return "soft", last_sentence

    def _detect_rhythm(self, text: str) -> str:
        """检测节奏"""
        avg_sentence_length = len(text) / max(text.count("。"), 1)

        if avg_sentence_length < 15:
            return "fast"
        elif avg_sentence_length < 30:
            return "medium"
        else:
            return "slow"

    def _detect_transitions(self, text: str) -> List[str]:
        """检测转折点"""
        transition_words = ["但是", "然而", "不过", "可是", "所以", "因此", "于是"]
        transitions = []

        for word in transition_words:
            if word in text:
                transitions.append(word)

        return transitions

    async def _analyze_emotion(self, text: str) -> EmotionAnalysis:
        """情感分析"""
        # TODO: 实际使用 LLM 或情感分析模型
        # 这里是简化实现

        # 检测主情绪
        primary_emotion = self._detect_primary_emotion(text)

        # 计算情绪强度
        emotion_intensity = self._calculate_emotion_intensity(text)

        # 生成情绪曲线（简化）
        emotion_curve = [(i * 20, 0.5 + (i % 3) * 0.1) for i in range(5)]

        # 提取触发词
        trigger_words = self._extract_trigger_words(text)

        # 计算情感分数
        sentiment_score = self._calculate_sentiment_score(text)

        return EmotionAnalysis(
            primary_emotion=primary_emotion,
            emotion_intensity=emotion_intensity,
            emotion_curve=emotion_curve,
            trigger_words=trigger_words,
            sentiment_score=sentiment_score
        )

    def _detect_primary_emotion(self, text: str) -> str:
        """检测主情绪"""
        emotion_keywords = {
            "joy": ["开心", "快乐", "幸福", "喜欢", "爱"],
            "surprise": ["惊喜", "意外", "没想到", "竟然"],
            "fear": ["担心", "害怕", "恐惧", "焦虑"],
            "anger": ["生气", "愤怒", "讨厌", "烦"],
            "sadness": ["难过", "伤心", "失望", "遗憾"],
            "trust": ["相信", "信任", "可靠", "专业"]
        }

        emotion_scores = {}
        for emotion, keywords in emotion_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text)
            emotion_scores[emotion] = score

        return max(emotion_scores, key=emotion_scores.get) if emotion_scores else "neutral"

    def _calculate_emotion_intensity(self, text: str) -> float:
        """计算情绪强度"""
        intensity_markers = ["！", "!", "？？", "太", "非常", "超级", "特别"]
        count = sum(text.count(marker) for marker in intensity_markers)
        return min(count / 10, 1.0)

    def _extract_trigger_words(self, text: str) -> List[str]:
        """提取触发词"""
        trigger_words = []
        high_emotion_words = ["惊喜", "震惊", "感动", "愤怒", "失望", "开心", "幸福"]

        for word in high_emotion_words:
            if word in text:
                trigger_words.append(word)

        return trigger_words[:5]

    def _calculate_sentiment_score(self, text: str) -> float:
        """计算情感分数"""
        positive_words = ["好", "棒", "赞", "喜欢", "爱", "开心", "幸福"]
        negative_words = ["差", "烂", "讨厌", "恨", "难过", "失望"]

        positive_count = sum(text.count(word) for word in positive_words)
        negative_count = sum(text.count(word) for word in negative_words)

        total = positive_count + negative_count
        if total == 0:
            return 0.0

        return (positive_count - negative_count) / total

    async def _analyze_topics(self, title: str, text: str) -> TopicAnalysis:
        """话题分析"""
        # TODO: 实际使用 LLM 或 NLP 模型
        # 这里是简化实现

        full_text = title + " " + text

        # 提取核心话题
        core_topics = self._extract_core_topics(full_text)

        # 检测热点话题
        hot_topics = self._detect_hot_topics(full_text)

        # 计算争议度
        controversy_level = self._calculate_controversy(full_text)

        # 提取痛点
        pain_points = self._extract_pain_points(full_text)

        # 提取关键词
        keywords = self._extract_keywords(full_text)

        return TopicAnalysis(
            core_topics=core_topics,
            hot_topics=hot_topics,
            controversy_level=controversy_level,
            pain_points=pain_points,
            keywords=keywords
        )

    def _extract_core_topics(self, text: str) -> List[str]:
        """提取核心话题"""
        # 简化实现：基于关键词匹配
        topic_keywords = {
            "美妆": ["护肤", "化妆", "美妆", "口红", "粉底"],
            "穿搭": ["穿搭", "服装", "搭配", "时尚", "衣服"],
            "美食": ["美食", "食谱", "做饭", "餐厅", "好吃"],
            "旅行": ["旅行", "旅游", "景点", "攻略", "打卡"],
            "健身": ["健身", "减肥", "运动", "瑜伽", "锻炼"]
        }

        topics = []
        for topic, keywords in topic_keywords.items():
            if any(keyword in text for keyword in keywords):
                topics.append(topic)

        return topics[:3]

    def _detect_hot_topics(self, text: str) -> List[str]:
        """检测热点话题"""
        # 简化实现：基于热点关键词
        hot_keywords = ["新品", "限定", "联名", "爆款", "网红", "热门"]
        hot_topics = [keyword for keyword in hot_keywords if keyword in text]
        return hot_topics[:3]

    def _calculate_controversy(self, text: str) -> float:
        """计算争议度"""
        controversy_markers = ["争议", "质疑", "反对", "批评", "不同意见"]
        count = sum(text.count(marker) for marker in controversy_markers)
        return min(count / 5, 1.0)

    def _extract_pain_points(self, text: str) -> List[str]:
        """提取痛点"""
        pain_keywords = ["困扰", "问题", "烦恼", "难题", "痛点", "焦虑"]
        pain_points = []

        for keyword in pain_keywords:
            if keyword in text:
                # 提取包含痛点关键词的句子
                sentences = text.split("。")
                for sentence in sentences:
                    if keyword in sentence:
                        pain_points.append(sentence.strip()[:50])
                        break

        return pain_points[:3]

    def _extract_keywords(self, text: str) -> List[Tuple[str, float]]:
        """提取关键词"""
        # 简化实现：基于词频
        import re
        from collections import Counter

        # 分词（简化）
        words = re.findall(r'[\u4e00-\u9fa5]+', text)
        words = [w for w in words if len(w) >= 2]

        # 统计词频
        word_counts = Counter(words)

        # 返回 Top-10
        return word_counts.most_common(10)

    async def _analyze_visual(self, cover_path: str) -> VisualAnalysis:
        """视觉分析"""
        # TODO: 实际使用视觉模型分析
        # 这里是简化实现

        return VisualAnalysis(
            layout="top_image_bottom_text",
            dominant_colors=["#FF6B6B", "#4ECDC4"],
            color_scheme="vibrant",
            objects=[{"name": "person", "confidence": 0.9}],
            text_regions=[{"text": "标题", "position": [10, 10, 200, 50]}],
            visual_style="professional",
            visual_score=0.8
        )

    def _default_visual(self) -> VisualAnalysis:
        """默认视觉分析"""
        return VisualAnalysis(
            layout="unknown",
            dominant_colors=[],
            color_scheme="neutral",
            objects=[],
            text_regions=[],
            visual_style="unknown",
            visual_score=0.5
        )

    async def _analyze_timing(
        self,
        publish_time: Optional[datetime],
        metrics: Optional[Dict[str, int]]
    ) -> TimingAnalysis:
        """时机分析"""
        if not publish_time:
            publish_time = datetime.now()

        publish_hour = publish_time.hour
        publish_day_of_week = publish_time.weekday()

        # 时间类别
        if 6 <= publish_hour < 9:
            time_category = "morning"
        elif 9 <= publish_hour < 12:
            time_category = "noon"
        elif 12 <= publish_hour < 18:
            time_category = "afternoon"
        elif 18 <= publish_hour < 22:
            time_category = "evening"
        else:
            time_category = "night"

        # 计算速度
        velocity_24h = 0.0
        if metrics:
            views = metrics.get('views', 0)
            hours_since_publish = (datetime.now() - publish_time).total_seconds() / 3600
            if hours_since_publish > 0:
                velocity_24h = views / hours_since_publish * 24

        # 时机分数（简化）
        timing_score = 0.7 if time_category in ["evening", "noon"] else 0.5

        return TimingAnalysis(
            publish_hour=publish_hour,
            publish_day_of_week=publish_day_of_week,
            time_category=time_category,
            velocity_24h=velocity_24h,
            peak_time=None,
            timing_score=timing_score
        )

    async def _analyze_audience(
        self,
        title: str,
        text: str,
        topics: TopicAnalysis
    ) -> AudienceAnalysis:
        """受众分析"""
        # TODO: 实际使用 LLM 分析
        # 这里是简化实现

        full_text = title + " " + text

        # 推断年龄段
        target_age_range = self._infer_age_range(full_text, topics)

        # 推断性别
        target_gender = self._infer_gender(full_text)

        # 提取兴趣
        interests = topics.core_topics + topics.hot_topics

        # 提取痛点
        pain_points = topics.pain_points

        # 提取愿望
        aspirations = self._extract_aspirations(full_text)

        # 受众匹配分数
        audience_match_score = 0.75

        return AudienceAnalysis(
            target_age_range=target_age_range,
            target_gender=target_gender,
            interests=interests,
            pain_points=pain_points,
            aspirations=aspirations,
            audience_match_score=audience_match_score
        )

    def _infer_age_range(self, text: str, topics: TopicAnalysis) -> Tuple[int, int]:
        """推断年龄段"""
        # 简化实现：基于话题
        if "学生" in text or "校园" in text:
            return (18, 25)
        elif "职场" in text or "工作" in text:
            return (25, 35)
        elif "妈妈" in text or "育儿" in text:
            return (28, 40)
        else:
            return (20, 35)

    def _infer_gender(self, text: str) -> str:
        """推断性别"""
        female_keywords = ["美妆", "护肤", "口红", "裙子", "包包"]
        male_keywords = ["游戏", "数码", "汽车", "球鞋"]

        female_count = sum(text.count(keyword) for keyword in female_keywords)
        male_count = sum(text.count(keyword) for keyword in male_keywords)

        if female_count > male_count * 2:
            return "female"
        elif male_count > female_count * 2:
            return "male"
        else:
            return "all"

    def _extract_aspirations(self, text: str) -> List[str]:
        """提取愿望"""
        aspiration_keywords = ["想要", "希望", "梦想", "目标", "追求"]
        aspirations = []

        for keyword in aspiration_keywords:
            if keyword in text:
                sentences = text.split("。")
                for sentence in sentences:
                    if keyword in sentence:
                        aspirations.append(sentence.strip()[:50])
                        break

        return aspirations[:3]

    def _calculate_overall_score(
        self,
        structure: StructureAnalysis,
        emotion: EmotionAnalysis,
        topics: TopicAnalysis,
        visual: VisualAnalysis,
        timing: TimingAnalysis,
        audience: AudienceAnalysis
    ) -> float:
        """计算综合分数"""
        weights = {
            'structure': 0.25,
            'emotion': 0.15,
            'topics': 0.15,
            'visual': 0.20,
            'timing': 0.10,
            'audience': 0.15
        }

        overall_score = (
            weights['structure'] * structure.overall_score +
            weights['emotion'] * (emotion.emotion_intensity + (emotion.sentiment_score + 1) / 2) / 2 +
            weights['topics'] * (1.0 - topics.controversy_level * 0.5) +
            weights['visual'] * visual.visual_score +
            weights['timing'] * timing.timing_score +
            weights['audience'] * audience.audience_match_score
        )

        return float(overall_score)

    def to_dict(self, analysis: ComprehensiveAnalysis) -> Dict[str, Any]:
        """转换为字典（用于存储到数据库）"""
        return {
            'structure': {
                'hook_type': analysis.structure.hook_type,
                'hook_text': analysis.structure.hook_text,
                'hook_score': analysis.structure.hook_score,
                'body_structure': analysis.structure.body_structure,
                'body_sections': analysis.structure.body_sections,
                'body_score': analysis.structure.body_score,
                'cta_type': analysis.structure.cta_type,
                'cta_text': analysis.structure.cta_text,
                'cta_score': analysis.structure.cta_score,
                'rhythm': analysis.structure.rhythm,
                'transitions': analysis.structure.transitions,
                'overall_score': analysis.structure.overall_score
            },
            'emotion': {
                'primary_emotion': analysis.emotion.primary_emotion,
                'emotion_intensity': analysis.emotion.emotion_intensity,
                'emotion_curve': analysis.emotion.emotion_curve,
                'trigger_words': analysis.emotion.trigger_words,
                'sentiment_score': analysis.emotion.sentiment_score
            },
            'topics': {
                'core_topics': analysis.topics.core_topics,
                'hot_topics': analysis.topics.hot_topics,
                'controversy_level': analysis.topics.controversy_level,
                'pain_points': analysis.topics.pain_points,
                'keywords': analysis.topics.keywords
            },
            'visual': {
                'layout': analysis.visual.layout,
                'dominant_colors': analysis.visual.dominant_colors,
                'color_scheme': analysis.visual.color_scheme,
                'objects': analysis.visual.objects,
                'text_regions': analysis.visual.text_regions,
                'visual_style': analysis.visual.visual_style,
                'visual_score': analysis.visual.visual_score
            },
            'timing': {
                'publish_hour': analysis.timing.publish_hour,
                'publish_day_of_week': analysis.timing.publish_day_of_week,
                'time_category': analysis.timing.time_category,
                'velocity_24h': analysis.timing.velocity_24h,
                'peak_time': analysis.timing.peak_time.isoformat() if analysis.timing.peak_time else None,
                'timing_score': analysis.timing.timing_score
            },
            'audience': {
                'target_age_range': list(analysis.audience.target_age_range),
                'target_gender': analysis.audience.target_gender,
                'interests': analysis.audience.interests,
                'pain_points': analysis.audience.pain_points,
                'aspirations': analysis.audience.aspirations,
                'audience_match_score': analysis.audience.audience_match_score
            }
        }
