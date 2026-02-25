"""
层级动作空间 - 可扩展的策略表示
Hierarchical Action Space: Strategy -> Implementation
"""

from typing import Dict, Any, List, Tuple, Optional
import logging
import random
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class StrategyType(str, Enum):
    """策略类型（高层）"""
    EMOTIONAL_RESONANCE = "emotional_resonance"  # 情绪共鸣
    KNOWLEDGE_AUTHORITY = "knowledge_authority"  # 知识权威
    SOCIAL_PROOF = "social_proof"  # 社交证明
    PROBLEM_SOLUTION = "problem_solution"  # 问题解决
    CURIOSITY_GAP = "curiosity_gap"  # 好奇缺口
    VALUE_PROPOSITION = "value_proposition"  # 价值主张
    STORYTELLING = "storytelling"  # 故事叙述
    DATA_DRIVEN = "data_driven"  # 数据驱动


@dataclass
class StrategyConfig:
    """策略配置"""
    type: StrategyType
    name: str
    description: str
    target_audience: List[str] = field(default_factory=list)  # 适合的受众
    platforms: List[str] = field(default_factory=list)  # 适合的平台
    success_rate: float = 0.5  # 历史成功率
    enabled: bool = True


@dataclass
class ImplementationTemplate:
    """实现模板（低层）"""
    id: str
    strategy_type: StrategyType
    hook_pattern: str
    body_pattern: str
    cta_pattern: str
    description: str
    examples: List[str] = field(default_factory=list)
    performance_score: float = 0.5  # 历史表现


class HierarchicalActionSpace:
    """
    层级动作空间

    两层结构：
    1. 高层：内容策略（Strategy）- 决定"做什么"
    2. 低层：实现模板（Implementation）- 决定"怎么做"

    优势：
    - 可扩展：新增策略不需要重构
    - 可学习：每个策略的实现可以独立优化
    - 可解释：策略和实现分离，更容易理解
    """

    def __init__(self):
        # 策略配置
        self.strategies: Dict[StrategyType, StrategyConfig] = {}
        self._init_strategies()

        # 实现模板
        self.implementations: Dict[StrategyType, List[ImplementationTemplate]] = {}
        self._init_implementations()

        logger.info(
            f"Hierarchical Action Space initialized: "
            f"{len(self.strategies)} strategies, "
            f"{sum(len(impls) for impls in self.implementations.values())} implementations"
        )

    def _init_strategies(self):
        """初始化策略"""

        strategies = [
            StrategyConfig(
                type=StrategyType.EMOTIONAL_RESONANCE,
                name="情绪共鸣",
                description="通过情绪连接引发共鸣",
                target_audience=["年轻人", "职场人", "家长"],
                platforms=["xiaohongshu", "douyin"],
                success_rate=0.75
            ),
            StrategyConfig(
                type=StrategyType.KNOWLEDGE_AUTHORITY,
                name="知识权威",
                description="通过专业知识建立权威",
                target_audience=["学习者", "专业人士"],
                platforms=["douyin", "bilibili"],
                success_rate=0.70
            ),
            StrategyConfig(
                type=StrategyType.SOCIAL_PROOF,
                name="社交证明",
                description="通过他人验证建立信任",
                target_audience=["消费者", "决策者"],
                platforms=["xiaohongshu", "douyin"],
                success_rate=0.72
            ),
            StrategyConfig(
                type=StrategyType.PROBLEM_SOLUTION,
                name="问题解决",
                description="提供具体问题的解决方案",
                target_audience=["有痛点的用户"],
                platforms=["xiaohongshu", "douyin", "bilibili"],
                success_rate=0.78
            ),
            StrategyConfig(
                type=StrategyType.CURIOSITY_GAP,
                name="好奇缺口",
                description="制造信息缺口引发好奇",
                target_audience=["泛娱乐用户"],
                platforms=["douyin", "tiktok"],
                success_rate=0.68
            ),
            StrategyConfig(
                type=StrategyType.VALUE_PROPOSITION,
                name="价值主张",
                description="明确传达产品/服务价值",
                target_audience=["潜在客户"],
                platforms=["xiaohongshu", "douyin"],
                success_rate=0.65
            ),
            StrategyConfig(
                type=StrategyType.STORYTELLING,
                name="故事叙述",
                description="通过故事传递信息",
                target_audience=["情感用户", "年轻人"],
                platforms=["xiaohongshu", "douyin"],
                success_rate=0.73
            ),
            StrategyConfig(
                type=StrategyType.DATA_DRIVEN,
                name="数据驱动",
                description="用数据和事实说话",
                target_audience=["理性用户", "专业人士"],
                platforms=["douyin", "bilibili"],
                success_rate=0.67
            )
        ]

        for strategy in strategies:
            self.strategies[strategy.type] = strategy

    def _init_implementations(self):
        """初始化实现模板"""

        # 情绪共鸣策略的实现
        self.implementations[StrategyType.EMOTIONAL_RESONANCE] = [
            ImplementationTemplate(
                id="ER_001",
                strategy_type=StrategyType.EMOTIONAL_RESONANCE,
                hook_pattern="痛点共鸣 + 情绪词",
                body_pattern="场景描述 + 情感递进",
                cta_pattern="情感呼应 + 互动",
                description="通过痛点引发共鸣",
                examples=["你是不是也经常...？", "每次遇到...都让人崩溃"],
                performance_score=0.78
            ),
            ImplementationTemplate(
                id="ER_002",
                strategy_type=StrategyType.EMOTIONAL_RESONANCE,
                hook_pattern="身份认同 + 情绪标签",
                body_pattern="群体画像 + 情感连接",
                cta_pattern="归属感召唤",
                description="通过身份认同建立连接",
                examples=["作为打工人，你懂的", "同为家长，我太理解了"],
                performance_score=0.75
            )
        ]

        # 知识权威策略的实现
        self.implementations[StrategyType.KNOWLEDGE_AUTHORITY] = [
            ImplementationTemplate(
                id="KA_001",
                strategy_type=StrategyType.KNOWLEDGE_AUTHORITY,
                hook_pattern="专业身份 + 反常识观点",
                body_pattern="专业分析 + 数据支撑",
                cta_pattern="专业建议 + 关注",
                description="通过专业身份建立权威",
                examples=["作为10年从业者，我要说...", "医生不会告诉你的..."],
                performance_score=0.72
            ),
            ImplementationTemplate(
                id="KA_002",
                strategy_type=StrategyType.KNOWLEDGE_AUTHORITY,
                hook_pattern="数据震撼 + 专业术语",
                body_pattern="深度解析 + 原理说明",
                cta_pattern="知识总结 + 收藏",
                description="通过深度内容展示专业",
                examples=["90%的人不知道...", "科学研究表明..."],
                performance_score=0.70
            )
        ]

        # 社交证明策略的实现
        self.implementations[StrategyType.SOCIAL_PROOF] = [
            ImplementationTemplate(
                id="SP_001",
                strategy_type=StrategyType.SOCIAL_PROOF,
                hook_pattern="用户数量 + 效果展示",
                body_pattern="真实案例 + 用户证言",
                cta_pattern="从众引导 + 转化",
                description="通过用户数量建立信任",
                examples=["10万人都在用...", "朋友圈都在推荐..."],
                performance_score=0.74
            ),
            ImplementationTemplate(
                id="SP_002",
                strategy_type=StrategyType.SOCIAL_PROOF,
                hook_pattern="明星/KOL背书",
                body_pattern="权威推荐 + 效果对比",
                cta_pattern="跟随行动",
                description="通过权威背书建立信任",
                examples=["XX明星同款", "XX博主力荐"],
                performance_score=0.76
            )
        ]

        # 问题解决策略的实现
        self.implementations[StrategyType.PROBLEM_SOLUTION] = [
            ImplementationTemplate(
                id="PS_001",
                strategy_type=StrategyType.PROBLEM_SOLUTION,
                hook_pattern="痛点问题 + 解决承诺",
                body_pattern="步骤拆解 + 避坑指南",
                cta_pattern="行动指令 + 效果预期",
                description="提供具体解决方案",
                examples=["还在为...烦恼？3步解决", "教你彻底解决..."],
                performance_score=0.80
            ),
            ImplementationTemplate(
                id="PS_002",
                strategy_type=StrategyType.PROBLEM_SOLUTION,
                hook_pattern="对比震撼 + 方法预告",
                body_pattern="前后对比 + 方法详解",
                cta_pattern="立即尝试",
                description="通过对比展示效果",
                examples=["用了这个方法后...", "前后对比太明显了"],
                performance_score=0.77
            )
        ]

        # 好奇缺口策略的实现
        self.implementations[StrategyType.CURIOSITY_GAP] = [
            ImplementationTemplate(
                id="CG_001",
                strategy_type=StrategyType.CURIOSITY_GAP,
                hook_pattern="悬念设置 + 反转预告",
                body_pattern="层层递进 + 意外揭秘",
                cta_pattern="悬念延续",
                description="制造信息缺口",
                examples=["你绝对想不到...", "最后一个太意外了"],
                performance_score=0.71
            ),
            ImplementationTemplate(
                id="CG_002",
                strategy_type=StrategyType.CURIOSITY_GAP,
                hook_pattern="反常识 + 疑问引导",
                body_pattern="打破认知 + 真相揭示",
                cta_pattern="评论区揭晓",
                description="挑战常识引发好奇",
                examples=["原来我们都错了", "真相竟然是..."],
                performance_score=0.69
            )
        ]

        # 价值主张策略的实现
        self.implementations[StrategyType.VALUE_PROPOSITION] = [
            ImplementationTemplate(
                id="VP_001",
                strategy_type=StrategyType.VALUE_PROPOSITION,
                hook_pattern="利益点前置 + 数字量化",
                body_pattern="价值拆解 + 对比凸显",
                cta_pattern="限时促销 + 转化",
                description="明确传达价值",
                examples=["省下XX元", "提升XX倍效率"],
                performance_score=0.68
            )
        ]

        # 故事叙述策略的实现
        self.implementations[StrategyType.STORYTELLING] = [
            ImplementationTemplate(
                id="ST_001",
                strategy_type=StrategyType.STORYTELLING,
                hook_pattern="场景开场 + 冲突引入",
                body_pattern="故事展开 + 情节转折",
                cta_pattern="情感升华 + 共鸣",
                description="通过故事传递信息",
                examples=["那天我遇到了...", "这是一个关于...的故事"],
                performance_score=0.75
            )
        ]

        # 数据驱动策略的实现
        self.implementations[StrategyType.DATA_DRIVEN] = [
            ImplementationTemplate(
                id="DD_001",
                strategy_type=StrategyType.DATA_DRIVEN,
                hook_pattern="数据震撼 + 趋势预告",
                body_pattern="数据分析 + 图表展示",
                cta_pattern="数据总结 + 收藏",
                description="用数据说话",
                examples=["数据显示...", "根据XX研究..."],
                performance_score=0.70
            )
        ]

    def sample_action(
        self,
        context: Optional[Dict[str, Any]] = None,
        strategy_type: Optional[StrategyType] = None
    ) -> Dict[str, Any]:
        """
        采样动作

        Args:
            context: 上下文（平台、受众等）
            strategy_type: 指定策略类型（可选）

        Returns:
            动作（包含策略和实现）
        """

        # 1. 选择策略
        if strategy_type:
            selected_strategy = self.strategies[strategy_type]
        else:
            selected_strategy = self._select_strategy(context)

        # 2. 选择实现
        implementation = self._select_implementation(selected_strategy.type, context)

        return {
            'strategy': {
                'type': selected_strategy.type.value,
                'name': selected_strategy.name,
                'description': selected_strategy.description
            },
            'implementation': {
                'id': implementation.id,
                'hook_pattern': implementation.hook_pattern,
                'body_pattern': implementation.body_pattern,
                'cta_pattern': implementation.cta_pattern,
                'description': implementation.description
            },
            'performance_score': implementation.performance_score
        }

    def _select_strategy(self, context: Optional[Dict[str, Any]]) -> StrategyConfig:
        """选择策略（基于上下文）"""

        if not context:
            # 随机选择
            return random.choice(list(self.strategies.values()))

        # 根据平台和受众过滤
        platform = context.get('platform', '')
        audience = context.get('target_audience', {})

        # 计算每个策略的适配度
        scores = {}
        for strategy_type, strategy in self.strategies.items():
            if not strategy.enabled:
                continue

            score = strategy.success_rate  # 基础分

            # 平台匹配加分
            if platform and platform in strategy.platforms:
                score += 0.2

            # 受众匹配加分 — keyword overlap between audience and strategy
            if audience:
                audience_tags = set()
                for v in audience.values():
                    if isinstance(v, str):
                        audience_tags.update(v.lower().split())
                    elif isinstance(v, list):
                        audience_tags.update(str(item).lower() for item in v)
                strategy_tags = set(strategy.description.lower().split()) if hasattr(strategy, 'description') else set()
                overlap = len(audience_tags & strategy_tags)
                score += min(overlap * 0.05, 0.2)

            scores[strategy_type] = score

        # 选择得分最高的
        if scores:
            best_strategy_type = max(scores, key=scores.get)
            return self.strategies[best_strategy_type]

        # 降级：随机选择
        return random.choice(list(self.strategies.values()))

    def _select_implementation(
        self,
        strategy_type: StrategyType,
        context: Optional[Dict[str, Any]]
    ) -> ImplementationTemplate:
        """选择实现模板"""

        implementations = self.implementations.get(strategy_type, [])

        if not implementations:
            # 降级：返回默认实现
            return ImplementationTemplate(
                id="DEFAULT",
                strategy_type=strategy_type,
                hook_pattern="通用Hook",
                body_pattern="通用Body",
                cta_pattern="通用CTA",
                description="默认实现"
            )

        # 根据历史表现选择（带探索）
        epsilon = 0.2  # 探索率

        if random.random() < epsilon:
            # 探索：随机选择
            return random.choice(implementations)
        else:
            # 利用：选择表现最好的
            return max(implementations, key=lambda x: x.performance_score)

    def add_strategy(self, strategy: StrategyConfig):
        """添加新策略"""
        self.strategies[strategy.type] = strategy
        if strategy.type not in self.implementations:
            self.implementations[strategy.type] = []

        logger.info(f"Strategy added: {strategy.name}")

    def add_implementation(self, implementation: ImplementationTemplate):
        """添加新实现"""
        if implementation.strategy_type not in self.implementations:
            self.implementations[implementation.strategy_type] = []

        self.implementations[implementation.strategy_type].append(implementation)

        logger.info(
            f"Implementation added: {implementation.id} "
            f"for strategy {implementation.strategy_type.value}"
        )

    def update_performance(self, implementation_id: str, performance_score: float):
        """更新实现的表现分数"""

        for implementations in self.implementations.values():
            for impl in implementations:
                if impl.id == implementation_id:
                    impl.performance_score = performance_score
                    logger.info(
                        f"Performance updated: {implementation_id} -> {performance_score:.3f}"
                    )
                    return

        logger.warning(f"Implementation not found: {implementation_id}")

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""

        return {
            'total_strategies': len(self.strategies),
            'enabled_strategies': sum(1 for s in self.strategies.values() if s.enabled),
            'total_implementations': sum(len(impls) for impls in self.implementations.values()),
            'strategies': [
                {
                    'type': s.type.value,
                    'name': s.name,
                    'success_rate': s.success_rate,
                    'implementations_count': len(self.implementations.get(s.type, []))
                }
                for s in self.strategies.values()
            ]
        }
