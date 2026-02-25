"""
多平台内容引擎 (Multi-Platform Engine)

负责：
1. 统一内容格式（UCF）
2. 平台适配器（XHS/Douyin/Bilibili）
3. 跨平台发布
4. 跨平台效果对比
"""

import logging
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, JSON, Enum as SQLEnum, Text
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from app.core.database import Base

logger = logging.getLogger(__name__)


class Platform(str, Enum):
    """平台类型"""
    XHS = 'xiaohongshu'  # 小红书
    DOUYIN = 'douyin'  # 抖音
    BILIBILI = 'bilibili'  # B站
    WEIBO = 'weibo'  # 微博
    WECHAT = 'wechat'  # 微信公众号


class ContentType(str, Enum):
    """内容类型"""
    TEXT = 'text'  # 纯文本
    IMAGE = 'image'  # 图文
    VIDEO = 'video'  # 视频
    AUDIO = 'audio'  # 音频


class AdaptationStatus(str, Enum):
    """适配状态"""
    PENDING = 'pending'
    ADAPTED = 'adapted'
    PUBLISHED = 'published'
    FAILED = 'failed'


# ==================== 数据库模型 ====================

class UnifiedContentRecord(Base):
    """统一内容记录表"""
    __tablename__ = 'unified_content_records'

    content_id = Column(String(64), primary_key=True, comment='内容ID')

    # 核心内容
    title = Column(String(512), nullable=False, comment='标题')
    body = Column(Text, nullable=False, comment='正文')
    hook = Column(Text, comment='Hook')
    call_to_action = Column(Text, comment='行动号召')

    # 内容类型
    content_type = Column(SQLEnum(ContentType), nullable=False, comment='内容类型')

    # 多模态资源
    cover_image_path = Column(String(1024), comment='封面图片路径')
    video_path = Column(String(1024), comment='视频路径')
    audio_path = Column(String(1024), comment='音频路径')
    additional_images = Column(JSON, comment='额外图片列表')

    # 元数据
    topic = Column(String(256), comment='话题')
    tags = Column(JSON, comment='标签列表')
    target_audience = Column(JSON, comment='目标受众')

    # 创建信息
    generation_id = Column(String(64), comment='生成ID')
    account_id = Column(String(64), comment='账号ID')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')

    # 元数据
    meta_data = Column(JSON, comment='其他元数据')


class PlatformAdaptation(Base):
    """平台适配记录表"""
    __tablename__ = 'platform_adaptations'

    adaptation_id = Column(String(64), primary_key=True, comment='适配ID')

    # 关联信息
    content_id = Column(String(64), nullable=False, comment='内容ID')
    platform = Column(SQLEnum(Platform), nullable=False, comment='平台')

    # 适配后的内容
    adapted_title = Column(String(512), comment='适配后标题')
    adapted_body = Column(Text, comment='适配后正文')
    adapted_tags = Column(JSON, comment='适配后标签')

    # 平台特定配置
    platform_config = Column(JSON, comment='平台配置')

    # 资源处理
    processed_cover = Column(String(1024), comment='处理后封面')
    processed_video = Column(String(1024), comment='处理后视频')
    processed_images = Column(JSON, comment='处理后图片列表')

    # 状态
    status = Column(SQLEnum(AdaptationStatus), default=AdaptationStatus.PENDING, comment='状态')
    adapted_at = Column(DateTime, comment='适配时间')

    # 发布信息
    platform_post_id = Column(String(128), comment='平台帖子ID')
    platform_url = Column(String(1024), comment='平台URL')
    published_at = Column(DateTime, comment='发布时间')

    # 元数据
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    meta_data = Column(JSON, comment='其他元数据')


class CrossPlatformPerformance(Base):
    """跨平台表现对比表"""
    __tablename__ = 'cross_platform_performance'

    performance_id = Column(String(64), primary_key=True, comment='表现ID')

    # 关联信息
    content_id = Column(String(64), nullable=False, comment='内容ID')
    adaptation_id = Column(String(64), nullable=False, comment='适配ID')
    platform = Column(SQLEnum(Platform), nullable=False, comment='平台')

    # 表现指标
    views = Column(Integer, default=0, comment='浏览量')
    likes = Column(Integer, default=0, comment='点赞数')
    comments = Column(Integer, default=0, comment='评论数')
    shares = Column(Integer, default=0, comment='分享数')
    engagement_rate = Column(Float, default=0.0, comment='互动率')

    # 相对表现
    relative_performance = Column(Float, comment='相对表现（vs 平台平均）')
    rank_percentile = Column(Float, comment='排名百分位')

    # 时间信息
    collected_at = Column(DateTime, default=datetime.now, comment='采集时间')

    # 元数据
    meta_data = Column(JSON, comment='其他元数据')


# ==================== 数据类 ====================

@dataclass
class UnifiedContent:
    """统一内容格式"""

    # 核心内容
    title: str
    body: str
    hook: str = ""
    call_to_action: str = ""

    # 内容类型
    content_type: ContentType = ContentType.IMAGE

    # 多模态资源
    cover_image_path: Optional[str] = None
    video_path: Optional[str] = None
    audio_path: Optional[str] = None
    additional_images: List[str] = field(default_factory=list)

    # 元数据
    topic: str = ""
    tags: List[str] = field(default_factory=list)
    target_audience: Dict = field(default_factory=dict)

    # 平台配置
    platform_configs: Dict[Platform, Dict] = field(default_factory=dict)


@dataclass
class PlatformContent:
    """平台特定内容"""
    platform: Platform
    title: str
    body: str
    tags: List[str]
    cover_path: Optional[str]
    video_path: Optional[str]
    images: List[str]
    config: Dict


@dataclass
class CrossPlatformComparison:
    """跨平台对比"""
    content_id: str
    platforms: List[Platform]
    performances: Dict[Platform, Dict]
    best_platform: Platform
    best_performance: float
    insights: List[str]


# ==================== 平台适配器基类 ====================

class PlatformAdapter(ABC):
    """平台适配器基类"""

    def __init__(self, platform: Platform):
        self.platform = platform

    @abstractmethod
    def adapt(self, content: UnifiedContent) -> PlatformContent:
        """适配内容到特定平台"""
        pass

    @abstractmethod
    def validate(self, content: PlatformContent) -> Tuple[bool, List[str]]:
        """验证内容是否符合平台规范"""
        pass

    @abstractmethod
    async def publish(self, content: PlatformContent, account_id: str) -> Dict:
        """发布到平台"""
        pass


# ==================== 小红书适配器 ====================

class XHSAdapter(PlatformAdapter):
    """小红书适配器"""

    def __init__(self):
        super().__init__(Platform.XHS)

    def adapt(self, content: UnifiedContent) -> PlatformContent:
        """适配到小红书"""

        # 1. 标题处理：保留 emoji，限制长度
        title = content.title[:50]  # 小红书标题限制

        # 2. 正文处理：分段 + 话题标签
        body = self._format_body(content.body, content.tags)

        # 3. 标签处理：转换为小红书话题格式
        tags = [f"#{tag}" for tag in content.tags[:10]]  # 最多10个标签

        # 4. 封面处理：3:4 比例
        cover_path = self._process_cover(content.cover_image_path, aspect_ratio="3:4")

        # 5. 图片处理：最多9张
        images = content.additional_images[:9]

        # 6. 平台配置
        config = content.platform_configs.get(Platform.XHS, {})

        return PlatformContent(
            platform=Platform.XHS,
            title=title,
            body=body,
            tags=tags,
            cover_path=cover_path,
            video_path=None,  # 小红书图文不需要视频
            images=images,
            config=config
        )

    def _format_body(self, body: str, tags: List[str]) -> str:
        """格式化正文"""
        # 分段
        paragraphs = body.split('\n')
        formatted = '\n\n'.join(p.strip() for p in paragraphs if p.strip())

        # 添加话题标签
        if tags:
            formatted += '\n\n' + ' '.join(f"#{tag}" for tag in tags[:5])

        return formatted

    def _process_cover(self, cover_path: Optional[str], aspect_ratio: str) -> Optional[str]:
        """处理封面"""
        if not cover_path:
            return None

        # TODO: 实际实现需要调整图片比例
        # 这里返回原路径
        return cover_path

    def validate(self, content: PlatformContent) -> Tuple[bool, List[str]]:
        """验证内容"""
        errors = []

        if len(content.title) > 50:
            errors.append("标题超过50字")

        if len(content.body) > 1000:
            errors.append("正文超过1000字")

        if len(content.images) > 9:
            errors.append("图片超过9张")

        return len(errors) == 0, errors

    async def publish(self, content: PlatformContent, account_id: str) -> Dict:
        """发布到小红书"""
        # TODO: 实际实现需要调用小红书 API
        logger.info(f"发布到小红书: {content.title}")

        return {
            'platform': Platform.XHS.value,
            'post_id': f"xhs_{datetime.now().timestamp()}",
            'url': f"https://www.xiaohongshu.com/explore/xxx",
            'status': 'published'
        }


# ==================== 抖音适配器 ====================

class DouyinAdapter(PlatformAdapter):
    """抖音适配器"""

    def __init__(self):
        super().__init__(Platform.DOUYIN)

    def adapt(self, content: UnifiedContent) -> PlatformContent:
        """适配到抖音"""

        # 1. 标题处理：简短（< 30 字）
        title = content.title[:30]

        # 2. 正文处理：简短描述
        body = content.body[:100]  # 抖音描述较短

        # 3. 标签处理：话题标签
        tags = [f"#{tag}" for tag in content.tags[:5]]

        # 4. 视频处理：9:16 竖屏
        video_path = self._process_video(content.video_path, aspect_ratio="9:16")

        # 5. 封面处理：从视频提取
        cover_path = self._extract_video_cover(video_path)

        # 6. 平台配置
        config = content.platform_configs.get(Platform.DOUYIN, {})

        return PlatformContent(
            platform=Platform.DOUYIN,
            title=title,
            body=body,
            tags=tags,
            cover_path=cover_path,
            video_path=video_path,
            images=[],  # 抖音主要是视频
            config=config
        )

    def _process_video(self, video_path: Optional[str], aspect_ratio: str) -> Optional[str]:
        """处理视频"""
        if not video_path:
            return None

        # TODO: 实际实现需要调整视频比例、添加字幕
        return video_path

    def _extract_video_cover(self, video_path: Optional[str]) -> Optional[str]:
        """提取视频封面"""
        if not video_path:
            return None

        # TODO: 实际实现需要从视频提取关键帧
        return f"{video_path}_cover.jpg"

    def validate(self, content: PlatformContent) -> Tuple[bool, List[str]]:
        """验证内容"""
        errors = []

        if len(content.title) > 30:
            errors.append("标题超过30字")

        if not content.video_path:
            errors.append("缺少视频")

        return len(errors) == 0, errors

    async def publish(self, content: PlatformContent, account_id: str) -> Dict:
        """发布到抖音"""
        # TODO: 实际实现需要调用抖音 API
        logger.info(f"发布到抖音: {content.title}")

        return {
            'platform': Platform.DOUYIN.value,
            'post_id': f"dy_{datetime.now().timestamp()}",
            'url': f"https://www.douyin.com/video/xxx",
            'status': 'published'
        }


# ==================== B站适配器 ====================

class BilibiliAdapter(PlatformAdapter):
    """B站适配器"""

    def __init__(self):
        super().__init__(Platform.BILIBILI)

    def adapt(self, content: UnifiedContent) -> PlatformContent:
        """适配到B站"""

        # 1. 标题处理：详细（可长）
        title = content.title[:80]  # B站标题可以较长

        # 2. 正文处理：详细描述
        body = content.body  # B站支持长文本

        # 3. 标签处理：关键词标签
        tags = content.tags[:10]  # B站标签不需要 #

        # 4. 视频处理：16:9 横屏
        video_path = self._process_video(content.video_path, aspect_ratio="16:9")

        # 5. 封面处理：16:9 比例
        cover_path = self._process_cover(content.cover_image_path, aspect_ratio="16:9")

        # 6. 平台配置
        config = content.platform_configs.get(Platform.BILIBILI, {})

        return PlatformContent(
            platform=Platform.BILIBILI,
            title=title,
            body=body,
            tags=tags,
            cover_path=cover_path,
            video_path=video_path,
            images=[],
            config=config
        )

    def _process_video(self, video_path: Optional[str], aspect_ratio: str) -> Optional[str]:
        """处理视频"""
        if not video_path:
            return None

        # TODO: 实际实现需要调整视频比例
        return video_path

    def _process_cover(self, cover_path: Optional[str], aspect_ratio: str) -> Optional[str]:
        """处理封面"""
        if not cover_path:
            return None

        # TODO: 实际实现需要调整图片比例
        return cover_path

    def validate(self, content: PlatformContent) -> Tuple[bool, List[str]]:
        """验证内容"""
        errors = []

        if len(content.title) > 80:
            errors.append("标题超过80字")

        if not content.video_path:
            errors.append("缺少视频")

        return len(errors) == 0, errors

    async def publish(self, content: PlatformContent, account_id: str) -> Dict:
        """发布到B站"""
        # TODO: 实际实现需要调用B站 API
        logger.info(f"发布到B站: {content.title}")

        return {
            'platform': Platform.BILIBILI.value,
            'post_id': f"bv_{datetime.now().timestamp()}",
            'url': f"https://www.bilibili.com/video/BVxxx",
            'status': 'published'
        }


# ==================== 多平台内容引擎 ====================

class MultiPlatformEngine:
    """
    多平台内容引擎

    功能：
    1. 统一内容格式
    2. 平台适配
    3. 跨平台发布
    4. 跨平台效果对比
    """

    def __init__(self, db: Session):
        self.db = db

        # 注册适配器
        self.adapters: Dict[Platform, PlatformAdapter] = {
            Platform.XHS: XHSAdapter(),
            Platform.DOUYIN: DouyinAdapter(),
            Platform.BILIBILI: BilibiliAdapter()
        }

    # ==================== 内容创建 ====================

    def create_unified_content(
        self,
        title: str,
        body: str,
        content_type: ContentType = ContentType.IMAGE,
        **kwargs
    ) -> str:
        """
        创建统一内容

        Args:
            title: 标题
            body: 正文
            content_type: 内容类型
            **kwargs: 其他参数

        Returns:
            content_id
        """
        import uuid

        content_id = f"content_{uuid.uuid4().hex[:16]}"

        record = UnifiedContentRecord(
            content_id=content_id,
            title=title,
            body=body,
            content_type=content_type,
            hook=kwargs.get('hook', ''),
            call_to_action=kwargs.get('call_to_action', ''),
            cover_image_path=kwargs.get('cover_image_path'),
            video_path=kwargs.get('video_path'),
            audio_path=kwargs.get('audio_path'),
            additional_images=kwargs.get('additional_images', []),
            topic=kwargs.get('topic', ''),
            tags=kwargs.get('tags', []),
            target_audience=kwargs.get('target_audience', {}),
            generation_id=kwargs.get('generation_id'),
            account_id=kwargs.get('account_id')
        )

        self.db.add(record)
        self.db.commit()

        logger.info(f"✅ 创建统一内容: {content_id}")

        return content_id

    # ==================== 平台适配 ====================

    async def adapt_to_platforms(
        self,
        content_id: str,
        platforms: List[Platform]
    ) -> Dict[Platform, str]:
        """
        适配到多个平台

        Args:
            content_id: 内容ID
            platforms: 平台列表

        Returns:
            平台 → 适配ID 的映射
        """
        import uuid

        # 获取统一内容
        record = self.db.query(UnifiedContentRecord).filter(
            UnifiedContentRecord.content_id == content_id
        ).first()

        if not record:
            raise ValueError(f"内容不存在: {content_id}")

        # 转换为 UnifiedContent
        unified_content = UnifiedContent(
            title=record.title,
            body=record.body,
            hook=record.hook or "",
            call_to_action=record.call_to_action or "",
            content_type=record.content_type,
            cover_image_path=record.cover_image_path,
            video_path=record.video_path,
            audio_path=record.audio_path,
            additional_images=record.additional_images or [],
            topic=record.topic or "",
            tags=record.tags or [],
            target_audience=record.target_audience or {}
        )

        # 适配到各平台
        adaptations = {}

        for platform in platforms:
            adapter = self.adapters.get(platform)

            if not adapter:
                logger.warning(f"不支持的平台: {platform}")
                continue

            # 适配
            platform_content = adapter.adapt(unified_content)

            # 验证
            is_valid, errors = adapter.validate(platform_content)

            if not is_valid:
                logger.error(f"适配验证失败 ({platform}): {errors}")
                continue

            # 保存适配记录
            adaptation_id = f"adapt_{uuid.uuid4().hex[:16]}"

            adaptation = PlatformAdaptation(
                adaptation_id=adaptation_id,
                content_id=content_id,
                platform=platform,
                adapted_title=platform_content.title,
                adapted_body=platform_content.body,
                adapted_tags=platform_content.tags,
                platform_config=platform_content.config,
                processed_cover=platform_content.cover_path,
                processed_video=platform_content.video_path,
                processed_images=platform_content.images,
                status=AdaptationStatus.ADAPTED,
                adapted_at=datetime.now()
            )

            self.db.add(adaptation)
            adaptations[platform] = adaptation_id

        self.db.commit()

        logger.info(f"✅ 适配到 {len(adaptations)} 个平台")

        return adaptations

    # ==================== 跨平台发布 ====================

    async def publish_to_platforms(
        self,
        content_id: str,
        platforms: List[Platform],
        account_id: str
    ) -> Dict[Platform, Dict]:
        """
        发布到多个平台

        Args:
            content_id: 内容ID
            platforms: 平台列表
            account_id: 账号ID

        Returns:
            平台 → 发布结果 的映射
        """
        # 1. 适配
        adaptations = await self.adapt_to_platforms(content_id, platforms)

        # 2. 发布
        results = {}

        for platform, adaptation_id in adaptations.items():
            # 获取适配记录
            adaptation = self.db.query(PlatformAdaptation).filter(
                PlatformAdaptation.adaptation_id == adaptation_id
            ).first()

            if not adaptation:
                continue

            # 构建平台内容
            platform_content = PlatformContent(
                platform=platform,
                title=adaptation.adapted_title,
                body=adaptation.adapted_body,
                tags=adaptation.adapted_tags or [],
                cover_path=adaptation.processed_cover,
                video_path=adaptation.processed_video,
                images=adaptation.processed_images or [],
                config=adaptation.platform_config or {}
            )

            # 发布
            adapter = self.adapters[platform]
            result = await adapter.publish(platform_content, account_id)

            # 更新适配记录
            adaptation.status = AdaptationStatus.PUBLISHED
            adaptation.platform_post_id = result.get('post_id')
            adaptation.platform_url = result.get('url')
            adaptation.published_at = datetime.now()

            results[platform] = result

        self.db.commit()

        logger.info(f"✅ 发布到 {len(results)} 个平台")

        return results

    # ==================== 跨平台对比 ====================

    async def compare_cross_platform_performance(
        self,
        content_id: str
    ) -> CrossPlatformComparison:
        """
        对比跨平台表现

        Args:
            content_id: 内容ID

        Returns:
            跨平台对比结果
        """
        # 获取所有平台的表现数据
        performances_data = self.db.query(CrossPlatformPerformance).filter(
            CrossPlatformPerformance.content_id == content_id
        ).all()

        if not performances_data:
            raise ValueError(f"没有表现数据: {content_id}")

        # 整理数据
        platforms = []
        performances = {}

        for perf in performances_data:
            platforms.append(perf.platform)
            performances[perf.platform] = {
                'views': perf.views,
                'likes': perf.likes,
                'comments': perf.comments,
                'shares': perf.shares,
                'engagement_rate': perf.engagement_rate,
                'relative_performance': perf.relative_performance
            }

        # 找出最佳平台
        best_platform = max(
            performances.items(),
            key=lambda x: x[1]['engagement_rate']
        )[0]

        best_performance = performances[best_platform]['engagement_rate']

        # 生成洞察
        insights = self._generate_insights(performances)

        comparison = CrossPlatformComparison(
            content_id=content_id,
            platforms=platforms,
            performances=performances,
            best_platform=best_platform,
            best_performance=best_performance,
            insights=insights
        )

        logger.info(f"✅ 跨平台对比完成: 最佳平台={best_platform.value}")

        return comparison

    def _generate_insights(self, performances: Dict[Platform, Dict]) -> List[str]:
        """生成洞察"""
        insights = []

        # 找出表现最好和最差的平台
        sorted_platforms = sorted(
            performances.items(),
            key=lambda x: x[1]['engagement_rate'],
            reverse=True
        )

        best = sorted_platforms[0]
        worst = sorted_platforms[-1]

        insights.append(
            f"{best[0].value} 表现最好，互动率 {best[1]['engagement_rate']:.2%}"
        )

        insights.append(
            f"{worst[0].value} 表现最差，互动率 {worst[1]['engagement_rate']:.2%}"
        )

        # 对比差异
        if len(sorted_platforms) > 1:
            diff = best[1]['engagement_rate'] - worst[1]['engagement_rate']
            insights.append(
                f"最佳与最差平台互动率相差 {diff:.2%}"
            )

        return insights


# ==================== 使用示例 ====================

async def example_usage():
    """使用示例"""
    from app.db import get_db

    db = next(get_db())

    # 1. 创建引擎
    engine = MultiPlatformEngine(db)

    # 2. 创建统一内容
    content_id = engine.create_unified_content(
        title="冬季护肤攻略",
        body="分享我的冬季护肤心得...",
        content_type=ContentType.IMAGE,
        cover_image_path="/path/to/cover.jpg",
        tags=["护肤", "冬季", "保湿"],
        topic="护肤"
    )

    print(f"创建内容: {content_id}")

    # 3. 发布到多平台
    results = await engine.publish_to_platforms(
        content_id=content_id,
        platforms=[Platform.XHS, Platform.DOUYIN, Platform.BILIBILI],
        account_id='account_001'
    )

    print(f"发布结果: {results}")

    # 4. 对比跨平台表现（发布后一段时间）
    # comparison = await engine.compare_cross_platform_performance(content_id)
    # print(f"最佳平台: {comparison.best_platform.value}")
    # print(f"洞察: {comparison.insights}")
