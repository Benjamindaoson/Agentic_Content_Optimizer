"""
系统升级集成初始化模块
System Upgrade Integration Initializer
"""

import logging
from typing import Optional, Dict, Any

from app.core.config import get_settings
from app.core.config_manager import get_config_manager

logger = logging.getLogger(__name__)


class SystemUpgradeIntegration:
    """系统升级集成管理器"""

    def __init__(self):
        self.settings = get_settings()
        self.config_manager = get_config_manager(self.settings.SYSTEM_UPGRADE_CONFIG_PATH)

        # 组件实例
        self.reward_model = None
        self.experience_pool = None
        self.trend_agent = None
        self.tracer = None
        self.model_router = None
        self.action_space = None

        logger.info("System Upgrade Integration initialized")

    def initialize_reward_model(self, goal_weights: Optional[Dict[str, float]] = None):
        """初始化奖励模型"""
        from app.ml.rl.hybrid_reward_model_v2 import HybridRewardModelV2 as RewardModel

        use_hybrid = self.config_manager.is_feature_enabled('hybrid_reward')
        hybrid_config = self.config_manager.get_hybrid_reward_config()

        self.reward_model = RewardModel(
            goal_weights=goal_weights,
            use_hybrid_model=use_hybrid,
            hybrid_config=hybrid_config
        )

        logger.info(f"Reward Model initialized (hybrid={'enabled' if use_hybrid else 'disabled'})")
        return self.reward_model

    def initialize_experience_pool(
        self,
        max_size: int = 1000,
        max_episodes: int = 100
    ):
        """初始化经验池"""
        from app.ml.rl.experience_pool import ExperiencePool

        use_diversity = self.config_manager.is_feature_enabled('diversity_experience_pool')
        diversity_config = self.config_manager.get_diversity_pool_config()

        self.experience_pool = ExperiencePool(
            max_size=max_size,
            max_episodes=max_episodes,
            use_diversity_aware=use_diversity,
            diversity_config=diversity_config
        )

        logger.info(f"Experience Pool initialized (diversity={'enabled' if use_diversity else 'disabled'})")
        return self.experience_pool

    def initialize_trend_agent(self, config: Optional[Any] = None):
        """初始化趋势代理"""
        from app.agents.content.trend_agent import TrendAgent

        use_filter = self.config_manager.is_feature_enabled('trend_quality_filter')
        filter_config = self.config_manager.get_trend_filter_config()

        self.trend_agent = TrendAgent(
            config=config,
            use_quality_filter=use_filter,
            filter_config=filter_config
        )

        logger.info(f"Trend Agent initialized (quality_filter={'enabled' if use_filter else 'disabled'})")
        return self.trend_agent

    def initialize_tracer(self, db_session: Optional[Any] = None):
        """初始化生成追踪器"""
        if not self.config_manager.is_feature_enabled('generation_tracer'):
            logger.info("Generation Tracer disabled")
            return None

        from app.core.tracer import GenerationTracer

        self.tracer = GenerationTracer(db_session=db_session)

        logger.info("Generation Tracer initialized")
        return self.tracer

    def initialize_model_router(self):
        """初始化模型路由器"""
        if not self.config_manager.is_feature_enabled('model_router'):
            logger.info("Model Router disabled")
            return None

        from app.engine.llm.model_router import ModelRouter, ModelConfig, RoutingRule, CanaryConfig, TaskType

        router_config = self.config_manager.config.model_router

        # 构建模型配置
        models = {}
        for name, config in router_config.models.items():
            models[name] = ModelConfig(
                name=name,
                provider=config['provider'],
                version=config['version'],
                max_tokens=config.get('max_tokens', 4000),
                temperature=config.get('temperature', 0.7),
                timeout=config.get('timeout', 30.0),
                cost_per_1k_tokens=config.get('cost_per_1k_tokens', 0.01)
            )

        # 构建路由规则
        routing_rules = []
        for rule in router_config.routing_rules:
            routing_rules.append(RoutingRule(
                task_type=TaskType(rule['task_type']),
                primary_model=rule['primary_model'],
                fallback_models=rule.get('fallback_models', [])
            ))

        # 构建灰度配置
        canary_config = CanaryConfig(
            enabled=router_config.canary.get('enabled', False),
            canary_model=router_config.canary.get('canary_model', ''),
            traffic_percent=router_config.canary.get('traffic_percent', 10.0),
            success_threshold=router_config.canary.get('success_threshold', 0.95),
            min_requests=router_config.canary.get('min_requests', 100)
        )

        self.model_router = ModelRouter(
            models=models,
            routing_rules=routing_rules,
            canary_config=canary_config
        )

        logger.info("Model Router initialized")
        return self.model_router

    def initialize_hierarchical_action_space(self):
        """初始化层级动作空间"""
        if not self.config_manager.is_feature_enabled('hierarchical_action_space'):
            logger.info("Hierarchical Action Space disabled")
            return None

        from app.ml.rl.hierarchical_action_space import HierarchicalActionSpace

        self.action_space = HierarchicalActionSpace()

        logger.info("Hierarchical Action Space initialized")
        return self.action_space

    def initialize_all(self, db_session: Optional[Any] = None):
        """初始化所有组件"""
        logger.info("Initializing all system upgrade components...")

        self.initialize_reward_model()
        self.initialize_experience_pool()
        self.initialize_trend_agent()
        self.initialize_tracer(db_session)
        self.initialize_model_router()
        self.initialize_hierarchical_action_space()

        logger.info("All system upgrade components initialized")

        return {
            'reward_model': self.reward_model,
            'experience_pool': self.experience_pool,
            'trend_agent': self.trend_agent,
            'tracer': self.tracer,
            'model_router': self.model_router,
            'action_space': self.action_space
        }

    def get_status(self) -> Dict[str, Any]:
        """获取集成状态"""
        return {
            'version': self.settings.VERSION,
            'features': {
                'hybrid_reward': self.config_manager.is_feature_enabled('hybrid_reward'),
                'trend_quality_filter': self.config_manager.is_feature_enabled('trend_quality_filter'),
                'diversity_experience_pool': self.config_manager.is_feature_enabled('diversity_experience_pool'),
                'model_router': self.config_manager.is_feature_enabled('model_router'),
                'generation_tracer': self.config_manager.is_feature_enabled('generation_tracer'),
                'hierarchical_action_space': self.config_manager.is_feature_enabled('hierarchical_action_space')
            },
            'components': {
                'reward_model': self.reward_model is not None,
                'experience_pool': self.experience_pool is not None,
                'trend_agent': self.trend_agent is not None,
                'tracer': self.tracer is not None,
                'model_router': self.model_router is not None,
                'action_space': self.action_space is not None
            }
        }


# 全局集成实例
_integration: Optional[SystemUpgradeIntegration] = None


def get_integration() -> SystemUpgradeIntegration:
    """获取集成管理器单例"""
    global _integration

    if _integration is None:
        _integration = SystemUpgradeIntegration()

    return _integration


def initialize_system_upgrade(db_session: Optional[Any] = None):
    """初始化系统升级"""
    integration = get_integration()
    return integration.initialize_all(db_session)
