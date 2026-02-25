"""
混合奖励模型 V2 演示

展示如何使用升级后的奖励系统
"""

import logging
from pathlib import Path

from app.ml.rl.hybrid_reward_model_v2 import HybridRewardModelV2
from app.ml.rl.real_metric_predictors import RealMetricPredictorEnsemble

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def demo_basic_usage():
    """基础使用演示"""
    logger.info("=" * 60)
    logger.info("演示 1: 基础使用")
    logger.info("=" * 60)

    # 创建模型（不加载预训练模型）
    model = HybridRewardModelV2(
        predictor_model_dir=None,  # 不加载预训练模型
        deployment_mode="full"
    )

    # 测试内容
    content = {
        'hook': '限时优惠！立即抢购',
        'body': '这款产品经过专家验证，效果显著。99%的用户都给予好评。',
        'cta': '点击了解更多'
    }

    context = {
        'target_geo': 'US',
        'action': {
            'hook_id': 0,
            'body_id': 1,
            'cta_id': 2
        }
    }

    critic_eval = {
        'overall_score': 0.85,
        'dimension_scores': {
            'creativity': 0.8,
            'engagement_potential': 0.9,
            'platform_fit': 0.85
        }
    }

    # 计算奖励
    breakdown = model.calculate_reward(
        content=content,
        context=context,
        critic_eval=critic_eval,
        action=context['action']
    )

    # 显示结果
    logger.info(f"\n总奖励: {breakdown.total_reward:.4f}")
    logger.info(f"\n奖励分解:")
    logger.info(f"  1. 真实世界奖励 (60%): {breakdown.real_world_reward:.4f}")
    logger.info(f"     - CTR: {breakdown.real_metrics['ctr']:.4f}")
    logger.info(f"     - 完播率: {breakdown.real_metrics['completion_rate']:.4f}")
    logger.info(f"     - 互动率: {breakdown.real_metrics['engagement_rate']:.4f}")
    logger.info(f"     - 转化率: {breakdown.real_metrics['conversion_rate']:.4f}")

    logger.info(f"\n  2. 内容质量奖励 (30%): {breakdown.quality_reward:.4f}")
    logger.info(f"     - Critic 评分: {breakdown.quality_components['critic_score']:.4f}")
    logger.info(f"     - 结构评分: {breakdown.quality_components['structure_score']:.4f}")

    logger.info(f"\n  3. 系统健康奖励 (10%): {breakdown.system_health_reward:.4f}")
    logger.info(f"     - 多样性: {breakdown.health_components['diversity']:.4f}")
    logger.info(f"     - 新颖度: {breakdown.health_components['novelty']:.4f}")
    logger.info(f"     - GEO 适配: {breakdown.health_components['geo']:.4f}")


def demo_deployment_modes():
    """部署模式演示"""
    logger.info("\n" + "=" * 60)
    logger.info("演示 2: 渐进式部署")
    logger.info("=" * 60)

    content = {
        'hook': '新品上市',
        'body': '独家设计，限量发售',
        'cta': '立即购买'
    }

    context = {'target_geo': 'CN', 'action': {'hook_id': 1, 'body_id': 2, 'cta_id': 0}}
    critic_eval = {'overall_score': 0.75}
    old_reward = 0.65  # 旧模型的奖励

    # 1. 影子模式
    logger.info("\n1. 影子模式（Shadow Mode）")
    logger.info("   - 新模型运行但不使用")
    logger.info("   - 用于收集对比数据")

    model_shadow = HybridRewardModelV2(deployment_mode="shadow")
    reward_shadow = model_shadow.calculate_hybrid_reward(
        content, context, critic_eval, context['action'], old_reward
    )
    logger.info(f"   返回奖励: {reward_shadow:.4f} (使用旧模型)")

    # 2. 混合模式
    logger.info("\n2. 混合模式（Hybrid Mode）")
    logger.info("   - 新旧模型线性插值")
    logger.info("   - 逐步提升新模型权重")

    for alpha in [0.1, 0.3, 0.5, 0.7, 0.9]:
        model_hybrid = HybridRewardModelV2(deployment_mode="hybrid")
        model_hybrid.set_deployment_mode("hybrid", alpha=alpha)

        reward_hybrid = model_hybrid.calculate_hybrid_reward(
            content, context, critic_eval, context['action'], old_reward
        )
        logger.info(f"   alpha={alpha:.1f}: {reward_hybrid:.4f}")

    # 3. 完全模式
    logger.info("\n3. 完全模式（Full Mode）")
    logger.info("   - 完全使用新模型")

    model_full = HybridRewardModelV2(deployment_mode="full")
    reward_full = model_full.calculate_hybrid_reward(
        content, context, critic_eval, context['action'], old_reward
    )
    logger.info(f"   返回奖励: {reward_full:.4f} (使用新模型)")


def demo_novelty_scoring():
    """新颖度评分演示"""
    logger.info("\n" + "=" * 60)
    logger.info("演示 3: 连续新颖度评分")
    logger.info("=" * 60)

    model = HybridRewardModelV2()

    # 生成一系列相似的内容
    logger.info("\n生成 5 条相似内容，观察新颖度变化:")

    for i in range(5):
        content = {
            'hook': f'限时优惠 {i+1}',
            'body': '这个产品改变了我的生活',
            'cta': '立即购买'
        }

        context = {'target_geo': 'US', 'action': {}}
        breakdown = model.calculate_reward(content, context, None, None)

        novelty = breakdown.health_components['novelty']
        logger.info(f"  内容 {i+1}: 新颖度 = {novelty:.4f}")

    # 生成一条完全不同的内容
    logger.info("\n生成 1 条完全不同的内容:")
    different_content = {
        'hook': '科学验证的方法',
        'body': '专家团队经过多年研究，终于找到了解决方案',
        'cta': '了解详情'
    }

    breakdown = model.calculate_reward(different_content, context, None, None)
    novelty = breakdown.health_components['novelty']
    logger.info(f"  不同内容: 新颖度 = {novelty:.4f}")


def demo_with_trained_predictors():
    """使用训练好的预测器演示"""
    logger.info("\n" + "=" * 60)
    logger.info("演示 4: 使用训练好的预测器")
    logger.info("=" * 60)

    model_dir = "models/metric_predictors"
    model_path = Path(model_dir)

    if not model_path.exists():
        logger.warning(f"预测器模型不存在: {model_dir}")
        logger.info("请先运行: python scripts/train_metric_predictors.py")
        return

    # 加载预训练模型
    model = HybridRewardModelV2(predictor_model_dir=model_dir)

    # 测试内容
    test_cases = [
        {
            'name': '高质量内容',
            'content': {
                'hook': '限时优惠！',
                'body': '这个产品改变了我的生活',
                'cta': '立即购买'
            },
            'action': {'hook_id': 0, 'body_id': 0, 'cta_id': 0}
        },
        {
            'name': '中等质量内容',
            'content': {
                'hook': '你知道吗？',
                'body': '专家推荐的秘密方法',
                'cta': '了解更多'
            },
            'action': {'hook_id': 1, 'body_id': 1, 'cta_id': 1}
        },
        {
            'name': '低质量内容',
            'content': {
                'hook': '震惊！',
                'body': '99%的人都不知道',
                'cta': '点击查看'
            },
            'action': {'hook_id': 2, 'body_id': 2, 'cta_id': 4}
        }
    ]

    for case in test_cases:
        logger.info(f"\n{case['name']}:")
        logger.info(f"  Hook: {case['content']['hook']}")
        logger.info(f"  Body: {case['content']['body']}")
        logger.info(f"  CTA: {case['content']['cta']}")

        context = {'target_geo': 'US', 'action': case['action']}
        breakdown = model.calculate_reward(
            content=case['content'],
            context=context,
            critic_eval={'overall_score': 0.7},
            action=case['action']
        )

        logger.info(f"  总奖励: {breakdown.total_reward:.4f}")
        logger.info(f"  预测 CTR: {breakdown.real_metrics['ctr']:.4f}")
        logger.info(f"  预测完播率: {breakdown.real_metrics['completion_rate']:.4f}")
        logger.info(f"  预测转化率: {breakdown.real_metrics['conversion_rate']:.4f}")


def demo_statistics():
    """统计信息演示"""
    logger.info("\n" + "=" * 60)
    logger.info("演示 5: 统计信息")
    logger.info("=" * 60)

    model = HybridRewardModelV2(
        weights={'real_world': 0.6, 'quality': 0.3, 'system_health': 0.1},
        real_metric_weights={'ctr': 0.3, 'completion': 0.3, 'engagement': 0.2, 'conversion': 0.2},
        deployment_mode="hybrid"
    )

    model.set_deployment_mode("hybrid", alpha=0.7)

    # 生成一些内容以填充历史
    for i in range(10):
        content = {'hook': f'测试 {i}', 'body': f'内容 {i}', 'cta': '行动'}
        model.calculate_reward(content, {}, None, None)

    # 获取统计信息
    stats = model.get_statistics()

    logger.info("\n模型统计:")
    logger.info(f"  部署模式: {stats['deployment_mode']}")
    logger.info(f"  混合系数: {stats['hybrid_alpha']}")
    logger.info(f"  历史大小: {stats['history_size']}")
    logger.info(f"\n  三层权重:")
    for layer, weight in stats['weights'].items():
        logger.info(f"    - {layer}: {weight}")
    logger.info(f"\n  真实指标权重:")
    for metric, weight in stats['real_metric_weights'].items():
        logger.info(f"    - {metric}: {weight}")


def main():
    """运行所有演示"""
    logger.info("\n" + "=" * 80)
    logger.info("混合奖励模型 V2 - 完整演示")
    logger.info("=" * 80)

    try:
        demo_basic_usage()
        demo_deployment_modes()
        demo_novelty_scoring()
        demo_with_trained_predictors()
        demo_statistics()

        logger.info("\n" + "=" * 80)
        logger.info("所有演示完成！")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"演示过程中出错: {e}", exc_info=True)


if __name__ == '__main__':
    main()
