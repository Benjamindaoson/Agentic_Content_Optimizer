"""
系统升级使用示例
演示如何使用所有新功能
"""

import asyncio
import logging
from pathlib import Path

# 导入新模块
from app.ml.rl.hybrid_reward_model import HybridRewardModel
from app.core.tracer import GenerationTracer, TraceAnalyzer
from app.rag.trend_quality_filter import TrendQualityFilter, BrandGuidelines
from app.ml.rl.diversity_experience_pool import DiversityAwareExperiencePool
from app.llm.model_router import ModelRouter, ModelConfig, RoutingRule, CanaryConfig, TaskType
from app.testing.regression_suite import RegressionTestSuite
from app.ml.rl.hierarchical_action_space import HierarchicalActionSpace, StrategyType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_1_hybrid_reward_model():
    """示例 1: 使用混合奖励模型"""

    print("\n" + "="*60)
    print("示例 1: 混合奖励模型")
    print("="*60)

    # 初始化
    reward_model = HybridRewardModel(
        metric_weights={
            'ctr': 0.2,
            'completion': 0.3,
            'engagement': 0.3,
            'conversion': 0.2
        },
        quality_threshold=0.7,
        alpha=0.6,
        beta=0.4
    )

    # 生成的内容
    content = {
        'hook': '3个技巧让你的短视频播放量翻10倍！',
        'body': '1. 前3秒抓眼球\n2. 中间加悬念\n3. 结尾强互动',
        'cta': '学会这3招，你的视频也能爆！快点赞收藏试试看！'
    }

    # 上下文
    context = {
        'geo_keywords': ['短视频', '播放量', '技巧', '互动', '点赞']
    }

    # 计算奖励
    reward_result = reward_model.calculate_reward(content, context)

    print(f"\n总奖励: {reward_result['total_reward']}")
    print(f"\n预测指标:")
    for metric, value in reward_result['predicted_metrics'].items():
        print(f"  {metric}: {value}")

    print(f"\n惩罚:")
    for penalty_type, value in reward_result['penalties'].items():
        if penalty_type != 'total':
            print(f"  {penalty_type}: {value}")

    print(f"\n质量分数: {reward_result['quality_score']}")
    print(f"质量奖励: {reward_result['quality_bonus']}")


async def example_2_generation_tracer():
    """示例 2: 使用生成追踪系统"""

    print("\n" + "="*60)
    print("示例 2: 生成追踪系统")
    print("="*60)

    # 初始化
    tracer = GenerationTracer()

    # 开始追踪
    trace_id = tracer.start_trace(
        user_id="user_123",
        input_data={
            'topic': '短视频拍摄技巧',
            'platform': 'xiaohongshu'
        }
    )

    print(f"\n追踪ID: {trace_id}")

    # 追踪各个阶段
    tracer.trace_trend_retrieval(
        geo_keywords=['短视频', '拍摄', '技巧'],
        references=[{'id': 'ref_1', 'title': '参考内容1'}],
        quality_scores=[0.8]
    )

    tracer.trace_strategy_selection(
        actions=[{'hook': 'H01', 'body': 'B02', 'cta': 'C01'}],
        diversity_score=0.75,
        exploration=False
    )

    tracer.trace_content_generation(
        action={'hook': 'H01', 'body': 'B02', 'cta': 'C01'},
        model='claude',
        model_version='claude-3-5-sonnet',
        prompt='生成内容...',
        temperature=0.7,
        generated_content={'hook': '...', 'body': '...', 'cta': '...'}
    )

    tracer.trace_quality_evaluation(
        critic_scores={'overall': 0.8},
        reward_components={'quality': 0.8, 'predicted': 0.7},
        total_reward=0.75,
        approved=True
    )

    # 结束追踪
    await tracer.end_trace(output_data={'success': True})

    print(f"追踪完成: {trace_id}")


async def example_3_trend_quality_filter():
    """示例 3: 使用趋势质量过滤器"""

    print("\n" + "="*60)
    print("示例 3: 趋势质量过滤器")
    print("="*60)

    # 初始化品牌指南
    brand_guidelines = BrandGuidelines({
        'tone_keywords': ['专业', '可信', '创新'],
        'forbidden_words': ['低俗', '色情', '暴力'],
        'target_audience': {
            'age_range': [18, 35],
            'interests': ['短视频', '内容创作']
        }
    })

    # 初始化过滤器
    filter = TrendQualityFilter(brand_guidelines=brand_guidelines)

    # 模拟趋势数据
    trends = [
        {
            'id': 'trend_1',
            'content': '专业的短视频拍摄技巧分享',
            'platform': 'xiaohongshu',
            'publish_time': '2026-02-12T10:00:00',
            'author': {'followers': 100000, 'verified': True},
            'engagement': {'likes': 5000, 'comments': 200, 'shares': 100}
        },
        {
            'id': 'trend_2',
            'content': '低俗内容',  # 会被过滤
            'platform': 'douyin',
            'publish_time': '2026-02-10T10:00:00',
            'author': {'followers': 1000, 'verified': False},
            'engagement': {'likes': 100, 'comments': 10, 'shares': 5}
        }
    ]

    # 过滤趋势
    filtered_trends = filter.filter_trends(trends, threshold=0.6)

    print(f"\n原始趋势数: {len(trends)}")
    print(f"过滤后趋势数: {len(filtered_trends)}")

    for trend in filtered_trends:
        print(f"\n趋势ID: {trend['id']}")
        print(f"质量分数: {trend['quality_score']}")
        print(f"详细评分: {trend['quality_details']}")


async def example_4_diversity_experience_pool():
    """示例 4: 使用多样性感知经验池"""

    print("\n" + "="*60)
    print("示例 4: 多样性感知经验池")
    print("="*60)

    # 初始化
    pool = DiversityAwareExperiencePool(
        max_size=1000,
        max_episodes=100,
        novelty_decay=0.95
    )

    # 模拟添加经验
    from app.schemas.policy import Experience, Episode
    from datetime import datetime

    experiences = []
    for i in range(5):
        exp = Experience(
            experience_id=f"exp_{i}",
            episode_id="episode_1",
            action={'hook': f'H0{i%3+1}', 'body': f'B0{i%2+1}', 'cta': 'C01'},
            reward=0.5 + i * 0.1,
            approved=True,
            timestamp=datetime.now().isoformat()
        )
        experiences.append(exp)

    episode = Episode(
        episode_id="episode_1",
        experiences=experiences,
        avg_reward=0.7,
        created_at=datetime.now().isoformat()
    )

    pool.add_episode(episode)

    # 获取统计
    stats = pool.get_statistics()
    print(f"\n经验池统计:")
    print(f"  总经验数: {stats['total_experiences']}")
    print(f"  平均奖励: {stats['avg_reward']}")
    print(f"  多样性统计: {stats['diversity_stats']}")

    # 采样经验
    sampled = pool.sample_experiences(n=3, strategy='balanced')
    print(f"\n采样了 {len(sampled)} 条经验")


async def example_5_model_router():
    """示例 5: 使用模型路由器"""

    print("\n" + "="*60)
    print("示例 5: 模型路由器")
    print("="*60)

    # 配置模型
    models = {
        'claude': ModelConfig(
            name='claude',
            provider='claude',
            version='claude-3-5-sonnet',
            cost_per_1k_tokens=0.015
        ),
        'deepseek': ModelConfig(
            name='deepseek',
            provider='deepseek',
            version='deepseek-chat',
            cost_per_1k_tokens=0.001
        )
    }

    # 配置路由规则
    routing_rules = [
        RoutingRule(
            task_type=TaskType.CONTENT_GENERATION,
            primary_model='deepseek',
            fallback_models=['claude']
        )
    ]

    # 配置灰度
    canary_config = CanaryConfig(
        enabled=False,
        canary_model='gemini',
        traffic_percent=10.0
    )

    # 初始化路由器
    router = ModelRouter(
        models=models,
        routing_rules=routing_rules,
        canary_config=canary_config
    )

    print("\n模型路由器已初始化")
    print(f"模型数量: {len(models)}")
    print(f"路由规则数量: {len(routing_rules)}")
    print(f"灰度状态: {'启用' if canary_config.enabled else '禁用'}")

    # 获取指标
    metrics = router.get_metrics()
    print(f"\n当前指标: {metrics}")


async def example_6_regression_test():
    """示例 6: 使用回归测试系统"""

    print("\n" + "="*60)
    print("示例 6: 回归测试系统")
    print("="*60)

    # 初始化
    test_suite = RegressionTestSuite(
        test_cases_path="./tests/regression/test_cases.json"
    )

    print(f"\n测试用例数: {len(test_suite.test_cases)}")

    # 显示测试用例
    for i, tc in enumerate(test_suite.test_cases[:3], 1):
        print(f"\n测试用例 {i}:")
        print(f"  ID: {tc.id}")
        print(f"  名称: {tc.name}")
        print(f"  描述: {tc.description}")
        print(f"  质量阈值: {tc.quality_threshold}")

    print("\n注意: 实际运行测试需要提供 generation_func 和 evaluation_func")


async def example_7_hierarchical_action_space():
    """示例 7: 使用层级动作空间"""

    print("\n" + "="*60)
    print("示例 7: 层级动作空间")
    print("="*60)

    # 初始化
    action_space = HierarchicalActionSpace()

    # 获取统计
    stats = action_space.get_statistics()
    print(f"\n策略统计:")
    print(f"  总策略数: {stats['total_strategies']}")
    print(f"  启用策略数: {stats['enabled_strategies']}")
    print(f"  总实现数: {stats['total_implementations']}")

    print(f"\n策略列表:")
    for strategy in stats['strategies'][:5]:
        print(f"  - {strategy['name']}: 成功率={strategy['success_rate']}, 实现数={strategy['implementations_count']}")

    # 采样动作
    context = {
        'platform': 'xiaohongshu',
        'target_audience': {'age_range': [18, 35]}
    }

    action = action_space.sample_action(context=context)

    print(f"\n采样的动作:")
    print(f"  策略: {action['strategy']['name']}")
    print(f"  描述: {action['strategy']['description']}")
    print(f"  实现ID: {action['implementation']['id']}")
    print(f"  Hook模式: {action['implementation']['hook_pattern']}")
    print(f"  Body模式: {action['implementation']['body_pattern']}")
    print(f"  CTA模式: {action['implementation']['cta_pattern']}")
    print(f"  表现分数: {action['performance_score']}")


async def main():
    """运行所有示例"""

    print("\n" + "="*80)
    print("Growth Flywheel 2.5 - 系统升级示例")
    print("="*80)

    # 运行所有示例
    await example_1_hybrid_reward_model()
    await example_2_generation_tracer()
    await example_3_trend_quality_filter()
    await example_4_diversity_experience_pool()
    await example_5_model_router()
    await example_6_regression_test()
    await example_7_hierarchical_action_space()

    print("\n" + "="*80)
    print("所有示例运行完成！")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
