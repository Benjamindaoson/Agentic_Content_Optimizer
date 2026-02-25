"""
奖励系统 V2 集成测试

验证所有组件正常工作
"""

import logging
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_imports():
    """测试模块导入"""
    logger.info("=" * 60)
    logger.info("测试 1: 模块导入")
    logger.info("=" * 60)

    try:
        from app.ml.rl.real_metric_predictors import (
            RealMetricPredictorEnsemble,
            CTRPredictor,
            CompletionRatePredictor,
            EngagementRatePredictor,
            ConversionRatePredictor
        )
        logger.info("✅ real_metric_predictors 导入成功")

        from app.ml.rl.hybrid_reward_model_v2 import HybridRewardModelV2, RewardBreakdown
        logger.info("✅ hybrid_reward_model_v2 导入成功")

        from app.ml.rl.reward_model import RewardModel
        logger.info("✅ reward_model 导入成功")

        return True

    except Exception as e:
        logger.error(f"❌ 导入失败: {e}")
        return False


def test_predictor_training():
    """测试预测器训练"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 2: 预测器训练")
    logger.info("=" * 60)

    try:
        from app.ml.rl.real_metric_predictors import RealMetricPredictorEnsemble

        # 创建模拟数据
        contents = [
            {'hook': f'Hook {i}', 'body': f'Body {i}', 'cta': f'CTA {i}'}
            for i in range(100)
        ]
        actions = [
            {'hook_id': i % 5, 'body_id': i % 7, 'cta_id': i % 3}
            for i in range(100)
        ]
        labels = {
            'ctr': [0.05 + (i % 10) * 0.01 for i in range(100)],
            'completion_rate': [0.5 + (i % 10) * 0.03 for i in range(100)],
            'engagement_rate': [0.1 + (i % 10) * 0.02 for i in range(100)],
            'conversion_rate': [0.02 + (i % 10) * 0.005 for i in range(100)]
        }

        # 训练
        ensemble = RealMetricPredictorEnsemble()
        ensemble.train_all(contents, actions, labels)

        # 测试预测
        test_content = {'hook': 'Test', 'body': 'Test body', 'cta': 'Test CTA'}
        test_action = {'hook_id': 0, 'body_id': 0, 'cta_id': 0}

        predictions = ensemble.predict_all(test_content, test_action)

        logger.info("预测结果:")
        for metric, value in predictions.items():
            logger.info(f"  {metric}: {value:.4f}")
            assert 0 <= value <= 1, f"{metric} 超出范围"

        logger.info("✅ 预测器训练和预测成功")
        return True

    except Exception as e:
        logger.error(f"❌ 预测器测试失败: {e}", exc_info=True)
        return False


def test_hybrid_reward_v2():
    """测试混合奖励模型 V2"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 3: 混合奖励模型 V2")
    logger.info("=" * 60)

    try:
        from app.ml.rl.hybrid_reward_model_v2 import HybridRewardModelV2

        # 创建模型
        model = HybridRewardModelV2()

        # 测试内容
        content = {
            'hook': '限时优惠！',
            'body': '这个产品改变了我的生活',
            'cta': '立即购买'
        }

        context = {
            'target_geo': 'US',
            'action': {'hook_id': 0, 'body_id': 0, 'cta_id': 0}
        }

        critic_eval = {
            'overall_score': 0.8,
            'dimension_scores': {
                'creativity': 0.75,
                'engagement_potential': 0.85
            }
        }

        # 计算奖励
        breakdown = model.calculate_reward(
            content=content,
            context=context,
            critic_eval=critic_eval,
            action=context['action']
        )

        logger.info(f"总奖励: {breakdown.total_reward:.4f}")
        logger.info(f"真实世界奖励: {breakdown.real_world_reward:.4f}")
        logger.info(f"内容质量奖励: {breakdown.quality_reward:.4f}")
        logger.info(f"系统健康奖励: {breakdown.system_health_reward:.4f}")

        # 验证
        assert 0 <= breakdown.total_reward <= 2, "总奖励超出范围"
        assert 0 <= breakdown.real_world_reward <= 1, "真实世界奖励超出范围"
        assert 0 <= breakdown.quality_reward <= 1, "质量奖励超出范围"
        assert 0 <= breakdown.system_health_reward <= 1, "健康奖励超出范围"

        logger.info("✅ 混合奖励模型 V2 测试成功")
        return True

    except Exception as e:
        logger.error(f"❌ 混合奖励模型 V2 测试失败: {e}", exc_info=True)
        return False


def test_deployment_modes():
    """测试部署模式"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 4: 部署模式")
    logger.info("=" * 60)

    try:
        from app.ml.rl.hybrid_reward_model_v2 import HybridRewardModelV2

        content = {'hook': 'Test', 'body': 'Test', 'cta': 'Test'}
        context = {'target_geo': 'US', 'action': {}}
        old_reward = 0.65

        # 测试影子模式
        model_shadow = HybridRewardModelV2(deployment_mode="shadow")
        reward_shadow = model_shadow.calculate_hybrid_reward(
            content, context, None, None, old_reward
        )
        assert reward_shadow == old_reward, "影子模式应返回旧奖励"
        logger.info("✅ 影子模式测试通过")

        # 测试混合模式
        model_hybrid = HybridRewardModelV2(deployment_mode="hybrid")
        model_hybrid.set_deployment_mode("hybrid", alpha=0.5)
        reward_hybrid = model_hybrid.calculate_hybrid_reward(
            content, context, None, None, old_reward
        )
        assert reward_hybrid != old_reward, "混合模式应返回混合奖励"
        logger.info("✅ 混合模式测试通过")

        # 测试完全模式
        model_full = HybridRewardModelV2(deployment_mode="full")
        reward_full = model_full.calculate_hybrid_reward(
            content, context, None, None, old_reward
        )
        assert reward_full != old_reward, "完全模式应返回新奖励"
        logger.info("✅ 完全模式测试通过")

        logger.info("✅ 所有部署模式测试成功")
        return True

    except Exception as e:
        logger.error(f"❌ 部署模式测试失败: {e}", exc_info=True)
        return False


def test_reward_model_integration():
    """测试 RewardModel 集成"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 5: RewardModel 集成")
    logger.info("=" * 60)

    try:
        from app.ml.rl.reward_model import RewardModel
        from app.schemas.evaluation import CriticEvaluation, DimensionScore, EvaluationDimension

        # 创建 RewardModel（启用 V2）
        reward_model = RewardModel(
            use_hybrid_v2=True,
            hybrid_v2_config={
                'predictor_model_dir': None,  # 不加载预训练模型
                'deployment_mode': 'full'
            }
        )

        # 创建测试数据
        critic_eval = CriticEvaluation(
            overall_score=0.8,
            dimension_scores=[
                DimensionScore(dimension=EvaluationDimension.CREATIVITY, score=0.75, reasoning="Good creativity shown"),
                DimensionScore(dimension=EvaluationDimension.ENGAGEMENT_POTENTIAL, score=0.85, reasoning="Great engagement potential"),
                DimensionScore(dimension=EvaluationDimension.PLATFORM_FIT, score=0.80, reasoning="Good platform fit"),
                DimensionScore(dimension=EvaluationDimension.EXECUTABILITY, score=0.75, reasoning="Executable content"),
                DimensionScore(dimension=EvaluationDimension.GEO_OPTIMIZATION, score=0.70, reasoning="Good GEO optimization")
            ],
            strengths=["Creative", "Engaging"],
            weaknesses=["Could be more specific"],
            suggestions=["Keep it up"],
            approval_status="approved",
            summary="Good content overall"
        )

        content = {
            'hook': '限时优惠',
            'body': '产品介绍',
            'cta': '立即购买'
        }

        action = {'hook_id': 0, 'body_id': 0, 'cta_id': 0}

        # 计算奖励
        reward_score = reward_model.calculate_reward(
            critic_evaluation=critic_eval,
            generated_content=content,
            action=action,
            diversity_score=0.8,
            context={'target_geo': 'US'}
        )

        logger.info(f"总奖励: {reward_score.total_reward}")
        logger.info(f"质量奖励: {reward_score.components.quality_reward}")
        logger.info(f"预测互动率: {reward_score.components.predicted_engagement}")

        # 验证
        assert reward_score.total_reward > 0, "总奖励应大于 0"
        assert 'hybrid_model_v2' in reward_score.calculation_details, "应使用 V2 模型"

        logger.info("✅ RewardModel 集成测试成功")
        return True

    except Exception as e:
        logger.error(f"❌ RewardModel 集成测试失败: {e}", exc_info=True)
        return False


def test_novelty_scoring():
    """测试新颖度评分"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 6: 新颖度评分")
    logger.info("=" * 60)

    try:
        from app.ml.rl.hybrid_reward_model_v2 import HybridRewardModelV2

        model = HybridRewardModelV2()

        # 生成相似内容
        novelty_scores = []
        for i in range(5):
            content = {
                'hook': f'限时优惠 {i}',
                'body': '这个产品改变了我的生活',
                'cta': '立即购买'
            }

            breakdown = model.calculate_reward(content, {}, None, None)
            novelty = breakdown.health_components['novelty']
            novelty_scores.append(novelty)

            logger.info(f"内容 {i+1} 新颖度: {novelty:.4f}")

        # 验证新颖度递减
        assert novelty_scores[0] > novelty_scores[-1], "新颖度应随相似内容增多而降低"

        # 生成完全不同的内容
        different_content = {
            'hook': '科学验证',
            'body': '专家团队研究成果',
            'cta': '了解详情'
        }

        breakdown = model.calculate_reward(different_content, {}, None, None)
        different_novelty = breakdown.health_components['novelty']

        logger.info(f"不同内容新颖度: {different_novelty:.4f}")
        assert different_novelty > novelty_scores[-1], "不同内容应有更高新颖度"

        logger.info("✅ 新颖度评分测试成功")
        return True

    except Exception as e:
        logger.error(f"❌ 新颖度评分测试失败: {e}", exc_info=True)
        return False


def main():
    """运行所有测试"""
    logger.info("\n" + "=" * 80)
    logger.info("奖励系统 V2 集成测试")
    logger.info("=" * 80)

    tests = [
        ("模块导入", test_imports),
        ("预测器训练", test_predictor_training),
        ("混合奖励模型 V2", test_hybrid_reward_v2),
        ("部署模式", test_deployment_modes),
        ("RewardModel 集成", test_reward_model_integration),
        ("新颖度评分", test_novelty_scoring)
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            logger.error(f"测试 '{name}' 异常: {e}", exc_info=True)
            results.append((name, False))

    # 总结
    logger.info("\n" + "=" * 80)
    logger.info("测试总结")
    logger.info("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{status} - {name}")

    logger.info(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        logger.info("\n🎉 所有测试通过！")
        return 0
    else:
        logger.error(f"\n❌ {total - passed} 个测试失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())
