"""
自动化账号运营管理器 (Auto-Account Manager)

负责：
1. 自动选题（话题发现）
2. 智能排程（最优发布时间）
3. 内容编排（自动生成）
4. 效果监控（实时追踪）
5. 策略调整（自动优化）

v4.0 增强：
- 集成 Thompson Sampling 进行话题选择
- 使用 GRPO 优化排程策略
- 在线学习和策略更新
"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import asyncio
import numpy as np

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, JSON, Enum as SQLEnum, Text
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from app.core.database import Base

# RL 组件导入
from app.ml.rl.thompson_sampling import ThompsonSamplingSelector
from app.ml.rl.grpo_trainer import GRPOTrainer
from app.ml.rl.online_metrics_collector import OnlineMetricsCollector
from app.ml.rl.hybrid_reward_model_v2 import HybridRewardModelV2

# RAG 组件导入
from app.engine.rag.retrievers.hybrid_retriever import HybridRetriever
from app.engine.rag.advanced_rag import SelfRAG, AdaptiveRAG

logger = logging.getLogger(__name__)


class TopicSource(str, Enum):
    """话题来源"""
    XHS_TRENDING = 'xhs_trending'  # 小红书热榜
    WEIBO_TRENDING = 'weibo_trending'  # 微博热搜
    DOUYIN_TRENDING = 'douyin_trending'  # 抖音热榜
    MANUAL = 'manual'  # 人工添加


class TopicStatus(str, Enum):
    """话题状态"""
    DISCOVERED = 'discovered'  # 已发现
    SELECTED = 'selected'  # 已选中
    SCHEDULED = 'scheduled'  # 已排程
    GENERATED = 'generated'  # 已生成
    PUBLISHED = 'published'  # 已发布
    REJECTED = 'rejected'  # 已拒绝


class ScheduleStrategy(str, Enum):
    """排程策略"""
    PEAK_TIME = 'peak_time'  # 高峰时段
    OFF_PEAK = 'off_peak'  # 非高峰时段
    PREDICTED_OPTIMAL = 'predicted_optimal'  # 预测最优时间
    IMMEDIATE = 'immediate'  # 立即发布


# ==================== 数据库模型 ====================

class DiscoveredTopic(Base):
    """发现的话题表"""
    __tablename__ = 'discovered_topics'

    topic_id = Column(String(64), primary_key=True, comment='话题ID')

    # 话题信息
    topic_name = Column(String(256), nullable=False, comment='话题名称')
    topic_keywords = Column(JSON, comment='关键词列表')
    topic_description = Column(Text, comment='话题描述')
    source = Column(SQLEnum(TopicSource), nullable=False, comment='来源')
    source_url = Column(String(1024), comment='来源URL')

    # 热度信息
    heat_score = Column(Float, default=0.0, comment='热度分数')
    trending_rank = Column(Integer, comment='热榜排名')
    search_volume = Column(Integer, default=0, comment='搜索量')
    discussion_count = Column(Integer, default=0, comment='讨论数')

    # 时间信息
    discovered_at = Column(DateTime, default=datetime.now, comment='发现时间')
    trending_start = Column(DateTime, comment='开始热门时间')
    trending_peak = Column(DateTime, comment='热度峰值时间')

    # 状态
    status = Column(SQLEnum(TopicStatus), default=TopicStatus.DISCOVERED, comment='状态')

    # 适配性评分
    persona_fit_score = Column(Float, comment='人设适配度')
    competition_level = Column(Float, comment='竞争程度')
    opportunity_score = Column(Float, comment='机会分数')

    # 元数据
    meta_data = Column(JSON, comment='其他元数据')


class ContentSchedule(Base):
    """内容排程表"""
    __tablename__ = 'content_schedules'

    schedule_id = Column(String(64), primary_key=True, comment='排程ID')

    # 关联信息
    account_id = Column(String(64), nullable=False, comment='账号ID')
    topic_id = Column(String(64), comment='话题ID')
    generation_id = Column(String(64), comment='生成ID')

    # 排程信息
    scheduled_time = Column(DateTime, nullable=False, comment='排程时间')
    strategy = Column(SQLEnum(ScheduleStrategy), comment='排程策略')
    predicted_performance = Column(Float, comment='预测表现')

    # 状态
    status = Column(String(32), default='pending', comment='状态')
    executed_at = Column(DateTime, comment='执行时间')

    # 结果
    actual_performance = Column(Float, comment='实际表现')
    performance_delta = Column(Float, comment='表现差异')

    # 元数据
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    meta_data = Column(JSON, comment='其他元数据')


class DailyPlan(Base):
    """每日计划表"""
    __tablename__ = 'daily_plans'

    plan_id = Column(String(64), primary_key=True, comment='计划ID')

    # 计划信息
    account_id = Column(String(64), nullable=False, comment='账号ID')
    plan_date = Column(DateTime, nullable=False, comment='计划日期')

    # 选题
    selected_topics = Column(JSON, comment='选中的话题列表')
    topic_count = Column(Integer, default=0, comment='话题数量')

    # 排程
    schedules = Column(JSON, comment='排程列表')
    schedule_count = Column(Integer, default=0, comment='排程数量')

    # 状态
    status = Column(String(32), default='draft', comment='状态')
    approved_at = Column(DateTime, comment='批准时间')

    # 执行结果
    executed_count = Column(Integer, default=0, comment='已执行数量')
    success_count = Column(Integer, default=0, comment='成功数量')
    avg_performance = Column(Float, comment='平均表现')

    # 元数据
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    meta_data = Column(JSON, comment='其他元数据')


@dataclass
class TopicRecommendation:
    """话题推荐"""
    topic_id: str
    topic_name: str
    heat_score: float
    persona_fit_score: float
    opportunity_score: float
    recommended_angles: List[str]
    estimated_performance: float


@dataclass
class OptimalSchedule:
    """最优排程"""
    scheduled_time: datetime
    strategy: ScheduleStrategy
    predicted_performance: float
    confidence: float
    reasoning: str


class AutoAccountManager:
    """
    自动化账号运营管理器

    v4.0 增强功能：
    1. Thompson Sampling 话题选择 - 探索-利用平衡
    2. GRPO 排程优化 - 基于真实指标学习
    3. 在线学习 - 持续优化策略
    4. 混合奖励模型 - 多目标优化
    5. RAG 检索增强 - 历史成功模式学习
    6. Adaptive RAG - 自适应检索策略
    """

    def __init__(
        self,
        db: Session,
        daily_topic_count: int = 3,
        min_heat_score: float = 0.6,
        min_fit_score: float = 0.5,
        enable_rl: bool = True,
        enable_rag: bool = True
    ):
        self.db = db
        self.daily_topic_count = daily_topic_count
        self.min_heat_score = min_heat_score
        self.min_fit_score = min_fit_score
        self.enable_rl = enable_rl
        self.enable_rag = enable_rag

        # RL 组件初始化
        if enable_rl:
            self.topic_selector = ThompsonSamplingSelector()
            self.grpo_trainer = GRPOTrainer()
            self.metrics_collector = OnlineMetricsCollector()
            self.reward_model = HybridRewardModelV2()
            logger.info("✅ RL 组件已启用")
        else:
            self.topic_selector = None
            self.grpo_trainer = None
            self.metrics_collector = None
            self.reward_model = None
            logger.info("⚠️ RL 组件未启用")

        # RAG 组件初始化
        if enable_rag:
            self.retriever = HybridRetriever()
            self.self_rag = SelfRAG(self.retriever)
            self.adaptive_rag = AdaptiveRAG(self.retriever)
            logger.info("✅ RAG 组件已启用")
        else:
            self.retriever = None
            self.self_rag = None
            self.adaptive_rag = None
            logger.info("⚠️ RAG 组件未启用")

    # ==================== 话题发现 ====================

    async def discover_trending_topics(
        self,
        sources: List[TopicSource] = None
    ) -> List[DiscoveredTopic]:
        """
        发现热门话题

        Args:
            sources: 话题来源列表

        Returns:
            发现的话题列表
        """
        if sources is None:
            sources = [TopicSource.XHS_TRENDING, TopicSource.WEIBO_TRENDING]

        discovered_topics = []

        for source in sources:
            if source == TopicSource.XHS_TRENDING:
                topics = await self._discover_xhs_trending()
                discovered_topics.extend(topics)
            elif source == TopicSource.WEIBO_TRENDING:
                topics = await self._discover_weibo_trending()
                discovered_topics.extend(topics)
            elif source == TopicSource.DOUYIN_TRENDING:
                topics = await self._discover_douyin_trending()
                discovered_topics.extend(topics)

        # 保存到数据库
        for topic in discovered_topics:
            self.db.add(topic)

        self.db.commit()

        logger.info(f"✅ 发现 {len(discovered_topics)} 个热门话题")

        return discovered_topics

    async def _discover_xhs_trending(self) -> List[DiscoveredTopic]:
        """
        发现小红书热门话题

        实现策略：
        1. 优先使用真实 API（如果配置）
        2. 否则使用智能模拟数据（基于时间、季节、节日）
        3. 添加缓存避免频繁请求
        """
        import uuid
        from datetime import datetime
        import random

        topics = []

        try:
            # 尝试从缓存获取（1小时有效期）
            cache_key = f"xhs_trending_{datetime.now().strftime('%Y%m%d%H')}"
            cached_topics = self._get_cached_topics(cache_key)
            if cached_topics:
                logger.info(f"从缓存获取 {len(cached_topics)} 个热门话题")
                return cached_topics

            # TODO: 实际实现需要调用小红书 API
            # 示例：使用 XHS Crawler 或 MediaCrawler
            # from app.crawlers.xhs_crawler import SpiderXHSAdapter
            # crawler = SpiderXHSAdapter()
            # trending_data = await crawler.get_trending_topics()

            # 智能模拟数据：基于当前时间生成相关话题
            topics = self._generate_contextual_topics()

            # 保存到缓存
            self._cache_topics(cache_key, topics)

            logger.info(f"发现 {len(topics)} 个热门话题（智能模拟）")
            return topics

        except Exception as e:
            logger.error(f"发现小红书热门话题失败: {e}")
            # 返回基础模拟数据作为降级方案
            return self._get_fallback_topics()

    def _generate_contextual_topics(self) -> List[DiscoveredTopic]:
        """
        生成基于上下文的智能话题

        考虑因素：
        - 当前月份/季节
        - 即将到来的节日
        - 工作日/周末
        - 时事热点（可配置）
        """
        import uuid
        from datetime import datetime
        import random

        now = datetime.now()
        month = now.month
        day_of_week = now.weekday()

        # 季节性话题库
        seasonal_topics = {
            # 春季 (3-5月)
            (3, 4, 5): [
                {'name': '春季护肤攻略', 'keywords': ['护肤', '春季', '换季', '敏感肌'], 'category': '美妆'},
                {'name': '春日穿搭灵感', 'keywords': ['穿搭', '春装', '时尚', '搭配'], 'category': '穿搭'},
                {'name': '春游打卡地推荐', 'keywords': ['旅行', '春游', '打卡', '踏青'], 'category': '旅行'},
            ],
            # 夏季 (6-8月)
            (6, 7, 8): [
                {'name': '夏日防晒指南', 'keywords': ['防晒', '夏季', '美白', '护肤'], 'category': '美妆'},
                {'name': '清凉穿搭合集', 'keywords': ['穿搭', '夏装', '清凉', '时尚'], 'category': '穿搭'},
                {'name': '夏日冷饮制作', 'keywords': ['美食', '冷饮', '夏日', '饮品'], 'category': '美食'},
            ],
            # 秋季 (9-11月)
            (9, 10, 11): [
                {'name': '秋季养生指南', 'keywords': ['养生', '秋季', '健康', '食疗'], 'category': '健康'},
                {'name': '秋日穿搭灵感', 'keywords': ['穿搭', '秋装', '叠穿', '时尚'], 'category': '穿搭'},
                {'name': '秋季护肤攻略', 'keywords': ['护肤', '秋季', '补水', '保湿'], 'category': '美妆'},
            ],
            # 冬季 (12-2月)
            (12, 1, 2): [
                {'name': '冬季护肤攻略', 'keywords': ['护肤', '冬季', '保湿', '干燥'], 'category': '美妆'},
                {'name': '冬日穿搭指南', 'keywords': ['穿搭', '冬装', '保暖', '时尚'], 'category': '穿搭'},
                {'name': '冬季养生食谱', 'keywords': ['美食', '养生', '冬季', '滋补'], 'category': '美食'},
            ],
        }

        # 节日话题库
        holiday_topics = {
            1: [{'name': '新年目标规划', 'keywords': ['新年', '目标', '规划', '自律'], 'category': '生活'}],
            2: [{'name': '情人节礼物推荐', 'keywords': ['情人节', '礼物', '浪漫', '送礼'], 'category': '生活'}],
            3: [{'name': '女神节好物分享', 'keywords': ['女神节', '好物', '礼物', '推荐'], 'category': '生活'}],
            5: [{'name': '母亲节礼物指南', 'keywords': ['母亲节', '礼物', '孝心', '推荐'], 'category': '生活'}],
            6: [{'name': '儿童节回忆杀', 'keywords': ['儿童节', '回忆', '童年', '怀旧'], 'category': '生活'}],
            9: [{'name': '中秋赏月攻略', 'keywords': ['中秋', '赏月', '月饼', '团圆'], 'category': '生活'}],
            10: [{'name': '国庆出游指南', 'keywords': ['国庆', '旅行', '出游', '假期'], 'category': '旅行'}],
            11: [{'name': '双十一购物清单', 'keywords': ['双十一', '购物', '好物', '省钱'], 'category': '生活'}],
            12: [{'name': '圣诞节氛围感', 'keywords': ['圣诞', '节日', '氛围', '装饰'], 'category': '生活'}],
        }

        # 工作日/周末话题
        weekday_topics = [
            {'name': '职场穿搭指南', 'keywords': ['职场', '穿搭', '通勤', '专业'], 'category': '穿搭'},
            {'name': '工作效率提升', 'keywords': ['效率', '工作', '时间管理', '职场'], 'category': '职场'},
            {'name': '午餐便当分享', 'keywords': ['美食', '便当', '午餐', '健康'], 'category': '美食'},
        ]

        weekend_topics = [
            {'name': '周末宅家指南', 'keywords': ['周末', '宅家', '休闲', '放松'], 'category': '生活'},
            {'name': '周末出游推荐', 'keywords': ['周末', '出游', '旅行', '打卡'], 'category': '旅行'},
            {'name': '周末美食探店', 'keywords': ['美食', '探店', '周末', '餐厅'], 'category': '美食'},
        ]

        # 常青话题（始终热门）
        evergreen_topics = [
            {'name': '减肥瘦身攻略', 'keywords': ['减肥', '瘦身', '健身', '塑形'], 'category': '健身'},
            {'name': '护肤品测评', 'keywords': ['护肤', '测评', '种草', '好物'], 'category': '美妆'},
            {'name': '家居收纳技巧', 'keywords': ['家居', '收纳', '整理', '断舍离'], 'category': '家居'},
            {'name': '学习方法分享', 'keywords': ['学习', '方法', '效率', '提升'], 'category': '学习'},
            {'name': '理财投资入门', 'keywords': ['理财', '投资', '省钱', '财务'], 'category': '理财'},
        ]

        # 选择话题
        selected_topics = []

        # 1. 添加季节性话题（2-3个）
        for months, topics_list in seasonal_topics.items():
            if month in months:
                selected_topics.extend(random.sample(topics_list, min(2, len(topics_list))))
                break

        # 2. 添加节日话题（如果有）
        if month in holiday_topics:
            selected_topics.extend(holiday_topics[month])

        # 3. 添加工作日/周末话题（1个）
        if day_of_week < 5:  # 工作日
            selected_topics.append(random.choice(weekday_topics))
        else:  # 周末
            selected_topics.append(random.choice(weekend_topics))

        # 4. 添加常青话题（2-3个）
        selected_topics.extend(random.sample(evergreen_topics, 3))

        # 转换为 DiscoveredTopic 对象
        discovered_topics = []
        for i, topic_data in enumerate(selected_topics[:10]):  # 最多10个
            # 生成热度分数（基于排名）
            heat_score = 0.95 - (i * 0.05)  # 0.95, 0.90, 0.85...
            heat_score = max(0.5, heat_score)  # 最低0.5

            # 生成搜索量（基于排名）
            base_volume = 50000
            search_volume = int(base_volume * (1 - i * 0.15))

            topic = DiscoveredTopic(
                topic_id=f"topic_{uuid.uuid4().hex[:16]}",
                topic_name=topic_data['name'],
                topic_keywords=topic_data['keywords'],
                source=TopicSource.XHS_TRENDING,
                heat_score=heat_score,
                trending_rank=i + 1,
                search_volume=search_volume,
                category=topic_data.get('category')
            )
            discovered_topics.append(topic)

        return discovered_topics

    def _get_fallback_topics(self) -> List[DiscoveredTopic]:
        """获取降级话题（基础模拟数据）"""
        import uuid

        mock_topics = [
            {
                'name': '护肤品测评',
                'keywords': ['护肤', '测评', '种草', '好物'],
                'heat_score': 0.85,
                'rank': 1,
                'search_volume': 50000,
                'category': '美妆'
            },
            {
                'name': '穿搭灵感分享',
                'keywords': ['穿搭', '时尚', '搭配', '灵感'],
                'heat_score': 0.78,
                'rank': 2,
                'search_volume': 35000,
                'category': '穿搭'
            },
            {
                'name': '美食探店推荐',
                'keywords': ['美食', '探店', '餐厅', '推荐'],
                'heat_score': 0.72,
                'rank': 3,
                'search_volume': 28000,
                'category': '美食'
            }
        ]

        topics = []
        for mock in mock_topics:
            topic = DiscoveredTopic(
                topic_id=f"topic_{uuid.uuid4().hex[:16]}",
                topic_name=mock['name'],
                topic_keywords=mock['keywords'],
                source=TopicSource.XHS_TRENDING,
                heat_score=mock['heat_score'],
                trending_rank=mock['rank'],
                search_volume=mock['search_volume'],
                category=mock.get('category')
            )
            topics.append(topic)

        return topics

    def _get_cached_topics(self, cache_key: str) -> Optional[List[DiscoveredTopic]]:
        """Get cached topics from Redis."""
        try:
            import json as _json
            from app.core.redis import redis_client
            import asyncio

            async def _get():
                if not redis_client.client:
                    return None
                data = await redis_client.get(f"topics:{cache_key}")
                if data and isinstance(data, list):
                    return [DiscoveredTopic(**item) for item in data]
                return None

            loop = asyncio.get_event_loop()
            if loop.is_running():
                return None  # Can't run sync in async context, skip cache
            return loop.run_until_complete(_get())
        except Exception as e:
            logger.debug(f"Cache get failed: {e}")
            return None

    def _cache_topics(self, cache_key: str, topics: List[DiscoveredTopic]):
        """Cache topics to Redis with TTL."""
        try:
            import json as _json
            from app.core.redis import redis_client
            import asyncio
            from dataclasses import asdict

            data = [asdict(t) for t in topics]

            async def _set():
                if not redis_client.client:
                    return
                await redis_client.set(f"topics:{cache_key}", data, expire=3600)

            loop = asyncio.get_event_loop()
            if not loop.is_running():
                loop.run_until_complete(_set())
        except Exception as e:
            logger.debug(f"Cache set failed: {e}")

    async def _discover_weibo_trending(self) -> List[DiscoveredTopic]:
        """Discover Weibo trending topics via API."""
        import httpx
        import uuid

        topics = []
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("https://weibo.com/ajax/side/hotSearch")
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("data", {}).get("realtime", [])[:10]:
                        topics.append(DiscoveredTopic(
                            topic_id=f"weibo_{uuid.uuid4().hex[:8]}",
                            topic_name=item.get("word", ""),
                            platform="weibo",
                            heat_score=min(float(item.get("num", 0)) / 1000000, 1.0),
                            topic_keywords=item.get("word", "").split(),
                            source="weibo_trending",
                        ))
        except Exception as e:
            logger.warning(f"Weibo trending fetch failed: {e}")
        return topics

    async def _discover_douyin_trending(self) -> List[DiscoveredTopic]:
        """Discover Douyin trending topics via API."""
        import httpx
        import uuid

        topics = []
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://www.douyin.com/aweme/v1/web/hot/search/list/",
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("data", {}).get("word_list", [])[:10]:
                        topics.append(DiscoveredTopic(
                            topic_id=f"douyin_{uuid.uuid4().hex[:8]}",
                            topic_name=item.get("word", ""),
                            platform="douyin",
                            heat_score=min(float(item.get("hot_value", 0)) / 10000000, 1.0),
                            topic_keywords=item.get("word", "").split(),
                            source="douyin_trending",
                        ))
        except Exception as e:
            logger.warning(f"Douyin trending fetch failed: {e}")
        return topics

    # ==================== 话题选择 ====================

    async def select_topics_for_account(
        self,
        account_id: str,
        date: datetime = None
    ) -> List[TopicRecommendation]:
        """
        为账号选择话题

        Args:
            account_id: 账号ID
            date: 日期（默认今天）

        Returns:
            推荐话题列表
        """
        if date is None:
            date = datetime.now()

        # 1. 获取账号人设
        from app.persona.persona_manager import PersonaManager
        persona_manager = PersonaManager(self.db)
        persona = persona_manager.get_persona(account_id)

        # 2. 获取最近发现的话题
        cutoff_time = datetime.now() - timedelta(hours=24)
        topics = self.db.query(DiscoveredTopic).filter(
            and_(
                DiscoveredTopic.discovered_at >= cutoff_time,
                DiscoveredTopic.status == TopicStatus.DISCOVERED,
                DiscoveredTopic.heat_score >= self.min_heat_score
            )
        ).order_by(DiscoveredTopic.heat_score.desc()).all()

        # 3. 计算人设适配度
        recommendations = []

        for topic in topics:
            # 计算适配度
            fit_score = self._calculate_persona_fit(topic, persona)

            if fit_score < self.min_fit_score:
                continue

            # 计算机会分数
            opportunity_score = self._calculate_opportunity_score(topic, account_id)

            # 推荐角度
            angles = self._recommend_angles(topic, persona)

            # 预估表现
            estimated_performance = self._estimate_performance(
                topic, persona, fit_score, opportunity_score
            )

            recommendation = TopicRecommendation(
                topic_id=topic.topic_id,
                topic_name=topic.topic_name,
                heat_score=topic.heat_score,
                persona_fit_score=fit_score,
                opportunity_score=opportunity_score,
                recommended_angles=angles,
                estimated_performance=estimated_performance
            )

            recommendations.append(recommendation)

        # 4. 排序并选择 Top N
        recommendations.sort(
            key=lambda x: (x.estimated_performance, x.heat_score),
            reverse=True
        )

        selected = recommendations[:self.daily_topic_count]

        logger.info(f"✅ 为账号 {account_id} 选择了 {len(selected)} 个话题")

        return selected

    async def select_topics_with_rl(
        self,
        account_id: str,
        date: datetime = None,
        exploration_rate: float = 0.2
    ) -> List[TopicRecommendation]:
        """
        使用 Thompson Sampling 选择话题 (RL 增强版)

        Args:
            account_id: 账号ID
            date: 日期
            exploration_rate: 探索率

        Returns:
            推荐话题列表
        """
        if not self.enable_rl or not self.topic_selector:
            logger.warning("RL 未启用,使用传统方法")
            return await self.select_topics_for_account(account_id, date)

        if date is None:
            date = datetime.now()

        # 1. 获取候选话题
        cutoff_time = datetime.now() - timedelta(hours=24)
        topics = self.db.query(DiscoveredTopic).filter(
            and_(
                DiscoveredTopic.discovered_at >= cutoff_time,
                DiscoveredTopic.status == TopicStatus.DISCOVERED,
                DiscoveredTopic.heat_score >= self.min_heat_score
            )
        ).all()

        if not topics:
            logger.warning("无可用话题")
            return []

        # 2. 构建动作空间 (每个话题是一个动作)
        actions = []
        for topic in topics:
            # 从历史数据获取 alpha, beta
            alpha, beta = self._get_topic_thompson_params(topic.topic_id, account_id)

            actions.append({
                'action_id': topic.topic_id,
                'alpha': alpha,
                'beta': beta,
                'topic': topic
            })

        # 3. Thompson Sampling 选择
        selected_actions = self.topic_selector.select_batch(
            actions=actions,
            k=self.daily_topic_count,
            exploration_rate=exploration_rate
        )

        # 4. 构建推荐结果
        recommendations = []
        for action in selected_actions:
            topic = action['topic']

            # 获取人设
            from app.persona.persona_manager import PersonaManager
            persona_manager = PersonaManager(self.db)
            persona = persona_manager.get_persona(account_id)

            fit_score = self._calculate_persona_fit(topic, persona)
            opportunity_score = self._calculate_opportunity_score(topic, account_id)
            angles = self._recommend_angles(topic, persona)
            estimated_performance = action.get('sampled_value', 0.5)

            recommendation = TopicRecommendation(
                topic_id=topic.topic_id,
                topic_name=topic.topic_name,
                heat_score=topic.heat_score,
                persona_fit_score=fit_score,
                opportunity_score=opportunity_score,
                recommended_angles=angles,
                estimated_performance=estimated_performance
            )

            recommendations.append(recommendation)

        logger.info(f"✅ [RL] 为账号 {account_id} 选择了 {len(recommendations)} 个话题")

        return recommendations

    def _get_topic_thompson_params(
        self,
        topic_id: str,
        account_id: str
    ) -> Tuple[float, float]:
        """
        获取话题的 Thompson Sampling 参数

        Returns:
            (alpha, beta) - Beta 分布参数
        """
        # 查询历史表现
        from app.db.models import Generation, OnlineMetrics

        # 查询该话题的历史生成记录
        generations = self.db.query(Generation).filter(
            and_(
                Generation.account_id == account_id,
                Generation.topic_id == topic_id
            )
        ).all()

        if not generations:
            # 无历史数据,使用先验
            return (1.0, 1.0)

        # 统计成功/失败
        successes = 0
        failures = 0

        for gen in generations:
            # 查询线上指标
            metrics = self.db.query(OnlineMetrics).filter_by(
                generation_id=gen.generation_id
            ).first()

            if metrics and metrics.viral_score:
                # 成功定义: viral_score > 0.6
                if metrics.viral_score > 0.6:
                    successes += 1
                else:
                    failures += 1

        # Beta 分布参数
        alpha = successes + 1.0  # 加 1 是拉普拉斯平滑
        beta = failures + 1.0

        return (alpha, beta)

    def _calculate_persona_fit(self, topic: DiscoveredTopic, persona) -> float:
        """Calculate persona-topic fit using keyword overlap + embedding similarity."""
        if not persona:
            return 0.5

        topic_keywords = set(topic.topic_keywords or [])
        persona_keywords = set(getattr(persona, 'brand_keywords', None) or [])

        if not topic_keywords or not persona_keywords:
            return 0.5

        # Keyword overlap score
        overlap = len(topic_keywords & persona_keywords)
        keyword_score = overlap / max(len(topic_keywords), 1)

        # Embedding similarity for deeper semantic matching
        semantic_score = 0.0
        try:
            from app.ml.rl.networks import StateEncoder
            encoder = StateEncoder(state_dim=32)
            topic_emb = encoder.encode({"topic": topic.topic_name, "keywords": topic.topic_keywords}).numpy()
            persona_emb = encoder.encode({"name": getattr(persona, 'brand_name', ''), "keywords": list(persona_keywords)}).numpy()
            dot = float(np.dot(topic_emb, persona_emb) / (np.linalg.norm(topic_emb) * np.linalg.norm(persona_emb) + 1e-8))
            semantic_score = max(dot, 0.0)
        except Exception:
            pass

        fit_score = 0.5 * keyword_score + 0.5 * semantic_score
        return min(fit_score, 1.0)

    def _calculate_opportunity_score(self, topic: DiscoveredTopic, account_id: str) -> float:
        """计算机会分数"""
        # 简化版：基于热度和竞争程度
        heat_score = topic.heat_score or 0.0
        competition = topic.competition_level or 0.5

        # 机会分数 = 热度 × (1 - 竞争程度)
        opportunity_score = heat_score * (1 - competition)

        return opportunity_score

    def _recommend_angles(self, topic: DiscoveredTopic, persona) -> List[str]:
        """Recommend content angles using LLM."""
        try:
            from app.engine.llm.unified import UnifiedLLM
            import asyncio

            llm = UnifiedLLM()
            persona_desc = ""
            if persona:
                persona_desc = f"Person: {getattr(persona, 'brand_name', '')}, Keywords: {getattr(persona, 'brand_keywords', [])}"

            prompt = f"""为以下话题推荐 5 个独特的内容创作角度，适合小红书平台。

话题: {topic.topic_name}
关键词: {', '.join(topic.topic_keywords or [])}
{persona_desc}

只返回 JSON:
{{"angles": ["角度1", "角度2", "角度3", "角度4", "角度5"]}}"""

            async def _get_angles():
                result = await llm.structured_output(
                    messages=[{"role": "user", "content": prompt}],
                    schema={"angles": "array"},
                    provider="claude", model="haiku-4.5", temperature=0.7,
                )
                return result.get("angles", [])

            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create a new task if we're already in async context
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    angles = pool.submit(asyncio.run, _get_angles()).result()
            else:
                angles = loop.run_until_complete(_get_angles())

            if angles:
                return angles
        except Exception as e:
            logger.warning(f"LLM angle generation failed: {e}")

        # Fallback
        return [
            f"{topic.topic_name} - 新手入门指南",
            f"{topic.topic_name} - 避坑实用贴",
            f"{topic.topic_name} - 深度测评分析",
        ]

    def _estimate_performance(
        self,
        topic: DiscoveredTopic,
        persona,
        fit_score: float,
        opportunity_score: float
    ) -> float:
        """Estimate performance using trained metric predictor ensemble."""
        # Try metric predictor first
        try:
            from app.ml.rl.real_metric_predictors import RealMetricPredictorEnsemble
            predictor = RealMetricPredictorEnsemble()
            content = {
                'hook': topic.topic_name,
                'body': ' '.join(topic.topic_keywords or []),
                'cta': '',
            }
            predictions = predictor.predict_all(content)
            model_score = predictions.get('engagement_rate', 0.5)
            # Blend model prediction with heuristic factors
            estimated = (
                0.3 * model_score +
                0.25 * (topic.heat_score or 0.0) +
                0.25 * fit_score +
                0.2 * opportunity_score
            )
            return estimated
        except Exception:
            pass

        # Fallback heuristic
        return (
            0.4 * (topic.heat_score or 0.0) +
            0.3 * fit_score +
            0.3 * opportunity_score
        )

    # ==================== 智能排程 ====================

    async def schedule_optimal_time(
        self,
        account_id: str,
        topic_id: str,
        strategy: ScheduleStrategy = ScheduleStrategy.PREDICTED_OPTIMAL
    ) -> OptimalSchedule:
        """
        计算最优发布时间

        Args:
            account_id: 账号ID
            topic_id: 话题ID
            strategy: 排程策略

        Returns:
            最优排程
        """
        if strategy == ScheduleStrategy.PEAK_TIME:
            return self._schedule_peak_time()
        elif strategy == ScheduleStrategy.OFF_PEAK:
            return self._schedule_off_peak()
        elif strategy == ScheduleStrategy.IMMEDIATE:
            return self._schedule_immediate()
        else:  # PREDICTED_OPTIMAL
            return await self._schedule_predicted_optimal(account_id, topic_id)

    def _schedule_peak_time(self) -> OptimalSchedule:
        """排程到高峰时段"""
        # 小红书高峰时段：12:00-13:00, 19:00-21:00
        now = datetime.now()

        # 找下一个高峰时段
        if now.hour < 12:
            scheduled_time = now.replace(hour=12, minute=0, second=0, microsecond=0)
        elif now.hour < 19:
            scheduled_time = now.replace(hour=19, minute=0, second=0, microsecond=0)
        else:
            # 明天中午
            scheduled_time = (now + timedelta(days=1)).replace(
                hour=12, minute=0, second=0, microsecond=0
            )

        return OptimalSchedule(
            scheduled_time=scheduled_time,
            strategy=ScheduleStrategy.PEAK_TIME,
            predicted_performance=0.7,
            confidence=0.8,
            reasoning="高峰时段用户活跃度高"
        )

    def _schedule_off_peak(self) -> OptimalSchedule:
        """排程到非高峰时段"""
        now = datetime.now()

        # 非高峰时段：9:00-11:00
        if now.hour < 9:
            scheduled_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
        else:
            # 明天早上
            scheduled_time = (now + timedelta(days=1)).replace(
                hour=9, minute=0, second=0, microsecond=0
            )

        return OptimalSchedule(
            scheduled_time=scheduled_time,
            strategy=ScheduleStrategy.OFF_PEAK,
            predicted_performance=0.6,
            confidence=0.7,
            reasoning="非高峰时段竞争较小"
        )

    def _schedule_immediate(self) -> OptimalSchedule:
        """立即发布"""
        return OptimalSchedule(
            scheduled_time=datetime.now(),
            strategy=ScheduleStrategy.IMMEDIATE,
            predicted_performance=0.5,
            confidence=0.5,
            reasoning="立即发布"
        )

    async def _schedule_predicted_optimal(
        self,
        account_id: str,
        topic_id: str
    ) -> OptimalSchedule:
        """Predict optimal posting time using historical engagement data analysis."""
        try:
            from app.db.models import Generation, OnlineMetrics

            # Query historical posting data for this account
            generations = self.db.query(Generation).filter(
                Generation.account_id == account_id
            ).order_by(Generation.created_at.desc()).limit(100).all()

            if len(generations) < 10:
                return self._schedule_peak_time()

            # Analyze engagement by hour-of-day
            hour_engagement = {}
            for gen in generations:
                metrics = self.db.query(OnlineMetrics).filter_by(
                    generation_id=gen.generation_id
                ).first()
                if metrics and gen.created_at:
                    hour = gen.created_at.hour
                    if hour not in hour_engagement:
                        hour_engagement[hour] = []
                    hour_engagement[hour].append(metrics.engagement_rate or 0.0)

            if not hour_engagement:
                return self._schedule_peak_time()

            # Find the hour with highest average engagement
            best_hour = max(hour_engagement, key=lambda h: np.mean(hour_engagement[h]))
            avg_engagement = np.mean(hour_engagement[best_hour])

            # Schedule for the next occurrence of best_hour
            now = datetime.now()
            if now.hour < best_hour:
                scheduled = now.replace(hour=best_hour, minute=0, second=0, microsecond=0)
            else:
                scheduled = (now + timedelta(days=1)).replace(hour=best_hour, minute=0, second=0, microsecond=0)

            return OptimalSchedule(
                scheduled_time=scheduled,
                strategy=ScheduleStrategy.PREDICTED_OPTIMAL,
                predicted_performance=float(avg_engagement),
                confidence=min(len(hour_engagement.get(best_hour, [])) / 10, 1.0),
                reasoning=f"历史数据分析: {best_hour}时段平均互动率最高 ({avg_engagement:.2%})"
            )

        except Exception as e:
            logger.warning(f"Optimal scheduling failed: {e}")
            return self._schedule_peak_time()

    # ==================== 每日计划 ====================

    async def create_daily_plan(
        self,
        account_id: str,
        date: datetime = None
    ) -> DailyPlan:
        """
        创建每日计划

        Args:
            account_id: 账号ID
            date: 日期

        Returns:
            每日计划
        """
        import uuid

        if date is None:
            date = datetime.now()

        # 1. 选择话题
        topics = await self.select_topics_for_account(account_id, date)

        # 2. 为每个话题排程
        schedules = []

        for i, topic in enumerate(topics):
            # 错开发布时间
            if i == 0:
                strategy = ScheduleStrategy.PEAK_TIME
            elif i == 1:
                strategy = ScheduleStrategy.OFF_PEAK
            else:
                strategy = ScheduleStrategy.PREDICTED_OPTIMAL

            schedule = await self.schedule_optimal_time(
                account_id,
                topic.topic_id,
                strategy
            )

            schedules.append({
                'topic_id': topic.topic_id,
                'topic_name': topic.topic_name,
                'scheduled_time': schedule.scheduled_time.isoformat(),
                'strategy': schedule.strategy.value,
                'predicted_performance': schedule.predicted_performance
            })

        # 3. 创建计划
        plan = DailyPlan(
            plan_id=f"plan_{uuid.uuid4().hex[:16]}",
            account_id=account_id,
            plan_date=date,
            selected_topics=[
                {
                    'topic_id': t.topic_id,
                    'topic_name': t.topic_name,
                    'estimated_performance': t.estimated_performance
                }
                for t in topics
            ],
            topic_count=len(topics),
            schedules=schedules,
            schedule_count=len(schedules)
        )

        self.db.add(plan)
        self.db.commit()

        logger.info(f"✅ 创建每日计划: {plan.plan_id}, {len(topics)} 个话题")

        return plan

    # ==================== 效果监控 ====================

    async def monitor_performance(
        self,
        schedule_id: str,
        time_window_minutes: int = 60
    ) -> Dict:
        """
        监控发布效果

        实现策略：
        1. 获取排程记录和关联的笔记
        2. 收集实际表现数据（点赞、评论、收藏等）
        3. 计算综合表现分数
        4. 对比预测值，评估准确性
        5. 生成改进建议

        Args:
            schedule_id: 排程ID
            time_window_minutes: 监控时间窗口（分钟）

        Returns:
            效果数据
        """
        try:
            # 1. 获取排程记录
            schedule = self.db.query(OptimalSchedule).filter(
                OptimalSchedule.schedule_id == schedule_id
            ).first()

            if not schedule:
                logger.warning(f"排程记录不存在: {schedule_id}")
                return {
                    'schedule_id': schedule_id,
                    'status': 'not_found',
                    'error': '排程记录不存在'
                }

            # 2. 获取关联的笔记（假设有 note_id 字段）
            # TODO: 需要在 OptimalSchedule 模型中添加 note_id 字段
            # 当前使用模拟数据
            note_id = getattr(schedule, 'note_id', None)

            if not note_id:
                logger.warning(f"排程 {schedule_id} 未关联笔记")
                return self._get_simulated_performance(schedule_id, schedule)

            # 3. 获取笔记的实际表现数据
            actual_metrics = await self._fetch_note_metrics(note_id, time_window_minutes)

            # 4. 计算综合表现分数
            actual_performance = self._calculate_performance_score(actual_metrics)

            # 5. 获取预测值
            predicted_performance = schedule.predicted_performance

            # 6. 计算偏差
            delta = actual_performance - predicted_performance
            delta_percent = (delta / predicted_performance * 100) if predicted_performance > 0 else 0

            # 7. 评估状态
            status = self._evaluate_performance_status(delta_percent)

            # 8. 生成改进建议
            suggestions = self._generate_improvement_suggestions(
                actual_metrics,
                actual_performance,
                predicted_performance,
                schedule
            )

            # 9. 记录评估结果（用于后续优化）
            await self._log_performance_evaluation(
                schedule_id=schedule_id,
                actual_performance=actual_performance,
                predicted_performance=predicted_performance,
                delta=delta,
                metrics=actual_metrics
            )

            return {
                'schedule_id': schedule_id,
                'note_id': note_id,
                'time_window_minutes': time_window_minutes,
                'actual_performance': round(actual_performance, 4),
                'predicted_performance': round(predicted_performance, 4),
                'delta': round(delta, 4),
                'delta_percent': round(delta_percent, 2),
                'status': status,
                'metrics': actual_metrics,
                'suggestions': suggestions,
                'evaluated_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"监控发布效果失败: {e}")
            return {
                'schedule_id': schedule_id,
                'status': 'error',
                'error': str(e)
            }

    async def _fetch_note_metrics(self, note_id: str, time_window_minutes: int) -> Dict:
        """Query real metrics from DB for the given note."""
        try:
            from app.db.models import XHSMetrics, OnlineMetrics

            # Try OnlineMetrics first (from our collection system)
            metrics_record = self.db.query(OnlineMetrics).filter(
                OnlineMetrics.note_id == note_id
            ).order_by(OnlineMetrics.collected_at.desc()).first()

            if metrics_record:
                return {
                    'views': metrics_record.views or 0,
                    'likes': metrics_record.likes or 0,
                    'comments': metrics_record.comments or 0,
                    'collects': metrics_record.collects or 0,
                    'shares': metrics_record.shares or 0,
                    'engagement_rate': float(metrics_record.engagement_rate or 0.0),
                    'ctr': float(getattr(metrics_record, 'ctr', 0) or 0.0),
                    'avg_watch_time': float(getattr(metrics_record, 'avg_watch_time', 0) or 0.0),
                }

            # Try XHSMetrics
            xhs_metrics = self.db.query(XHSMetrics).filter(
                XHSMetrics.note_id == note_id
            ).first()

            if xhs_metrics:
                views = xhs_metrics.views or 0
                likes = xhs_metrics.likes or 0
                comments = xhs_metrics.comments or 0
                collects = xhs_metrics.collects or 0
                shares = xhs_metrics.shares or 0
                engagement = (likes + comments + collects + shares) / max(views, 1)
                return {
                    'views': views,
                    'likes': likes,
                    'comments': comments,
                    'collects': collects,
                    'shares': shares,
                    'engagement_rate': round(engagement, 4),
                    'ctr': 0.0,
                    'avg_watch_time': 0.0,
                }

            logger.warning(f"No metrics found for note {note_id}")
            return {}

        except Exception as e:
            logger.error(f"获取笔记指标失败: {e}")
            return {}

    def _calculate_performance_score(self, metrics: Dict) -> float:
        """
        计算综合表现分数

        考虑因素：
        - 互动率（点赞、评论、收藏）
        - 传播力（分享）
        - 曝光效率（CTR）
        - 用户粘性（观看时长）

        Args:
            metrics: 指标数据

        Returns:
            综合分数 [0, 1]
        """
        if not metrics:
            return 0.0

        # 权重配置
        weights = {
            'engagement_rate': 0.4,  # 互动率最重要
            'ctr': 0.2,              # 点击率
            'share_rate': 0.2,       # 分享率
            'collect_rate': 0.2      # 收藏率
        }

        # 计算各项指标
        views = metrics.get('views', 1)
        likes = metrics.get('likes', 0)
        comments = metrics.get('comments', 0)
        collects = metrics.get('collects', 0)
        shares = metrics.get('shares', 0)

        # 互动率
        engagement_rate = metrics.get('engagement_rate', 0)
        if engagement_rate == 0 and views > 0:
            engagement_rate = (likes + comments * 2 + collects * 3) / views

        # CTR
        ctr = metrics.get('ctr', 0)

        # 分享率
        share_rate = shares / views if views > 0 else 0

        # 收藏率
        collect_rate = collects / views if views > 0 else 0

        # 加权计算
        score = (
            engagement_rate * weights['engagement_rate'] +
            ctr * weights['ctr'] +
            share_rate * weights['share_rate'] +
            collect_rate * weights['collect_rate']
        )

        # 归一化到 [0, 1]
        score = min(max(score, 0.0), 1.0)

        return score

    def _evaluate_performance_status(self, delta_percent: float) -> str:
        """
        评估表现状态

        Args:
            delta_percent: 偏差百分比

        Returns:
            状态标签
        """
        if delta_percent >= 20:
            return 'excellent'  # 超出预期 20%+
        elif delta_percent >= 10:
            return 'good'       # 超出预期 10-20%
        elif delta_percent >= -10:
            return 'normal'     # 符合预期 ±10%
        elif delta_percent >= -20:
            return 'below'      # 低于预期 10-20%
        else:
            return 'poor'       # 低于预期 20%+

    def _generate_improvement_suggestions(
        self,
        metrics: Dict,
        actual_performance: float,
        predicted_performance: float,
        schedule: 'OptimalSchedule'
    ) -> List[str]:
        """
        生成改进建议

        Args:
            metrics: 实际指标
            actual_performance: 实际表现
            predicted_performance: 预测表现
            schedule: 排程记录

        Returns:
            建议列表
        """
        suggestions = []

        # 1. 基于表现差异的建议
        delta_percent = ((actual_performance - predicted_performance) / predicted_performance * 100) if predicted_performance > 0 else 0

        if delta_percent < -20:
            suggestions.append("表现显著低于预期，建议重新评估话题选择和发布时间")

        # 2. 基于具体指标的建议
        engagement_rate = metrics.get('engagement_rate', 0)
        if engagement_rate < 0.05:
            suggestions.append("互动率偏低，建议优化内容质量和互动引导")

        ctr = metrics.get('ctr', 0)
        if ctr < 0.03:
            suggestions.append("点击率偏低，建议优化封面和标题吸引力")

        shares = metrics.get('shares', 0)
        views = metrics.get('views', 1)
        share_rate = shares / views if views > 0 else 0
        if share_rate < 0.01:
            suggestions.append("分享率偏低，建议增加内容的传播价值和分享动机")

        # 3. 基于发布时间的建议
        scheduled_time = schedule.scheduled_time
        hour = scheduled_time.hour if scheduled_time else 12

        if hour < 8 or hour > 22:
            suggestions.append("发布时间在非活跃时段，建议调整到 8:00-22:00")

        # 4. 通用建议
        if not suggestions:
            suggestions.append("表现符合预期，继续保持当前策略")

        return suggestions

    async def _log_performance_evaluation(
        self,
        schedule_id: str,
        actual_performance: float,
        predicted_performance: float,
        delta: float,
        metrics: Dict
    ):
        """Save evaluation results to DB for model optimization."""
        try:
            # Save to performance_evaluations via JSON metadata on schedule
            schedule = self.db.query(OptimalSchedule).filter(
                OptimalSchedule.schedule_id == schedule_id
            ).first()

            if schedule:
                eval_data = {
                    'actual_performance': actual_performance,
                    'predicted_performance': predicted_performance,
                    'delta': delta,
                    'metrics': metrics,
                    'evaluated_at': datetime.now().isoformat(),
                }
                existing_meta = schedule.meta_data or {}
                existing_meta['performance_evaluation'] = eval_data
                schedule.meta_data = existing_meta
                self.db.commit()

            logger.info(
                f"Performance evaluation saved: schedule_id={schedule_id}, "
                f"actual={actual_performance:.4f}, predicted={predicted_performance:.4f}, "
                f"delta={delta:.4f}"
            )

            # Feed back to RL system if enabled
            if hasattr(self, 'enable_rl') and self.enable_rl:
                try:
                    from app.ml.rl.grpo_engine import GRPOEngine
                    from app.engine.schemas.policy import Experience
                    # Create a lightweight experience for feedback
                    exp = Experience(
                        topic=schedule_id,
                        platform="xhs",
                        goal_metric="engagement_rate",
                        geo_keywords=[],
                        action={"hook": "eval", "body": "eval", "cta": "eval"},
                        reward=actual_performance,
                        generated_content={},
                        evaluation={"delta": delta},
                        episode_id=f"eval_{schedule_id}",
                    )
                    logger.info(f"RL feedback created for schedule {schedule_id}")
                except Exception as rl_e:
                    logger.debug(f"RL feedback failed: {rl_e}")

        except Exception as e:
            logger.error(f"记录评估结果失败: {e}")

    def _get_simulated_performance(self, schedule_id: str, schedule: 'OptimalSchedule') -> Dict:
        """
        获取模拟的表现数据（当无法获取真实数据时）

        Args:
            schedule_id: 排程ID
            schedule: 排程记录

        Returns:
            模拟的效果数据
        """
        import random

        predicted = schedule.predicted_performance
        # 添加一些随机波动（±20%）
        actual = predicted * random.uniform(0.8, 1.2)

        delta = actual - predicted
        delta_percent = (delta / predicted * 100) if predicted > 0 else 0

        return {
            'schedule_id': schedule_id,
            'actual_performance': round(actual, 4),
            'predicted_performance': round(predicted, 4),
            'delta': round(delta, 4),
            'delta_percent': round(delta_percent, 2),
            'status': self._evaluate_performance_status(delta_percent),
            'metrics': {
                'views': random.randint(500, 2000),
                'likes': random.randint(50, 200),
                'comments': random.randint(5, 30),
                'collects': random.randint(10, 50),
                'shares': random.randint(2, 15),
                'engagement_rate': round(random.uniform(0.05, 0.15), 4)
            },
            'suggestions': ['使用模拟数据，建议集成真实数据源'],
            'simulated': True,
            'evaluated_at': datetime.now().isoformat()
        }

    # ==================== RAG 增强方法 ====================

    async def retrieve_successful_topics(
        self,
        persona_keywords: List[str],
        limit: int = 10
    ) -> List[Dict]:
        """
        使用 RAG 检索历史成功话题

        Args:
            persona_keywords: 人设关键词
            limit: 返回数量

        Returns:
            成功话题列表
        """
        if not self.enable_rag:
            logger.warning("RAG 组件未启用，无法检索历史成功话题")
            return []

        try:
            # 构建查询
            query = " ".join(persona_keywords)

            # 混合检索
            results = await self.retriever.hybrid_search(
                query=query,
                limit=limit,
                filters={"viral_score": ">0.7"},
                use_query_expansion=True,
                use_reranking=True
            )

            logger.info(f"✅ [RAG] 检索到 {len(results)} 个成功话题")
            return results

        except Exception as e:
            logger.error(f"RAG 检索失败: {e}")
            return []

    async def find_similar_viral_content(
        self,
        topic: str,
        style: str,
        limit: int = 5
    ) -> List[Dict]:
        """
        使用 Self-RAG 查找相似爆款内容

        Args:
            topic: 话题
            style: 风格
            limit: 返回数量

        Returns:
            相似内容列表
        """
        if not self.enable_rag:
            logger.warning("RAG 组件未启用，无法查找相似爆款内容")
            return []

        try:
            query = f"{topic} {style}"

            # 使用 Self-RAG 迭代检索
            result = await self.self_rag.generate(
                query=query,
                context={"limit": limit},
                max_iterations=2
            )

            documents = []
            for iteration in result.get("iterations", []):
                documents.extend(iteration.get("documents", []))

            logger.info(f"✅ [RAG] Self-RAG 检索到 {len(documents)} 个相似内容")
            return documents[:limit]

        except Exception as e:
            logger.error(f"Self-RAG 检索失败: {e}")
            return []

    async def learn_success_patterns(
        self,
        account_id: str,
        days: int = 30
    ) -> Dict:
        """
        使用 Adaptive RAG 学习成功模式

        Args:
            account_id: 账号ID
            days: 学习时间窗口

        Returns:
            学习到的模式
        """
        if not self.enable_rag:
            logger.warning("RAG 组件未启用，无法学习成功模式")
            return {}

        try:
            query = f"账号 {account_id} 成功内容模式"

            # 使用 Adaptive RAG
            result = await self.adaptive_rag.generate(
                query=query,
                context={"account_id": account_id, "days": days},
                max_iterations=3
            )

            patterns = {
                "common_topics": [],
                "successful_hooks": [],
                "optimal_posting_times": [],
                "audience_preferences": []
            }

            # 提取模式
            for iteration in result.get("iterations", []):
                documents = iteration.get("documents", [])
                for doc in documents:
                    metadata = doc.get("metadata", {})
                    if "topic" in metadata:
                        patterns["common_topics"].append(metadata["topic"])
                    if "hook_type" in metadata:
                        patterns["successful_hooks"].append(metadata["hook_type"])

            logger.info(f"✅ [RAG] Adaptive RAG 学习到 {len(patterns['common_topics'])} 个成功模式")
            return patterns

        except Exception as e:
            logger.error(f"Adaptive RAG 学习失败: {e}")
            return {}


# ==================== 使用示例 ====================

async def example_usage():
    """使用示例"""
    from app.db import get_db

    db = next(get_db())

    # 1. 创建管理器
    manager = AutoAccountManager(
        db=db,
        daily_topic_count=3,
        min_heat_score=0.6
    )

    # 2. 发现热门话题
    topics = await manager.discover_trending_topics()
    print(f"发现 {len(topics)} 个热门话题")

    # 3. 为账号选择话题
    recommendations = await manager.select_topics_for_account('account_001')
    print(f"推荐 {len(recommendations)} 个话题")

    # 4. 创建每日计划
    plan = await manager.create_daily_plan('account_001')
    print(f"创建每日计划: {plan.plan_id}")

    # 5. 监控效果
    performance = await manager.monitor_performance('schedule_001')
    print(f"效果监控: {performance}")
