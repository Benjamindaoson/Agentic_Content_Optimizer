"""
训练真实指标预测器

使用 TikTok-10M 历史数据训练预测模型
"""

import argparse
import logging
from pathlib import Path
import json
import numpy as np
from typing import List, Dict, Any

from app.ml.rl.real_metric_predictors import RealMetricPredictorEnsemble

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_tiktok_data(data_path: str) -> tuple[List[Dict], List[Dict], Dict[str, List[float]]]:
    """
    加载 TikTok 数据

    Args:
        data_path: 数据文件路径

    Returns:
        (contents, actions, labels)
    """
    logger.info(f"加载数据: {data_path}")

    # 这里是示例实现，实际需要根据数据格式调整
    contents = []
    actions = []
    labels = {
        'ctr': [],
        'completion_rate': [],
        'engagement_rate': [],
        'conversion_rate': []
    }

    # 示例：从 JSONL 文件加载
    data_file = Path(data_path)
    if not data_file.exists():
        logger.warning(f"数据文件不存在: {data_path}，使用模拟数据")
        return generate_mock_data(1000)

    with open(data_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                item = json.loads(line)

                # 提取内容
                content = {
                    'hook': item.get('hook', ''),
                    'body': item.get('body', ''),
                    'cta': item.get('cta', '')
                }
                contents.append(content)

                # 提取动作
                action = {
                    'hook_id': item.get('hook_id', 0),
                    'body_id': item.get('body_id', 0),
                    'cta_id': item.get('cta_id', 0)
                }
                actions.append(action)

                # 提取标签
                stats = item.get('stats', {})
                labels['ctr'].append(stats.get('ctr', 0.0))
                labels['completion_rate'].append(stats.get('completion_rate', 0.0))
                labels['engagement_rate'].append(stats.get('engagement_rate', 0.0))
                labels['conversion_rate'].append(stats.get('conversion_rate', 0.0))

            except Exception as e:
                logger.warning(f"解析行失败: {e}")
                continue

    logger.info(f"✅ 加载了 {len(contents)} 条数据")
    return contents, actions, labels


def generate_mock_data(n_samples: int = 1000) -> tuple[List[Dict], List[Dict], Dict[str, List[float]]]:
    """
    生成模拟数据（用于测试）

    Args:
        n_samples: 样本数量

    Returns:
        (contents, actions, labels)
    """
    logger.info(f"生成 {n_samples} 条模拟数据")

    contents = []
    actions = []
    labels = {
        'ctr': [],
        'completion_rate': [],
        'engagement_rate': [],
        'conversion_rate': []
    }

    hooks = [
        "限时优惠！",
        "你知道吗？",
        "震惊！",
        "必看！",
        "独家揭秘",
        "新品上市",
        "免费领取",
        "立即查看"
    ]

    bodies = [
        "这个产品改变了我的生活",
        "专家推荐的秘密方法",
        "99%的人都不知道",
        "简单三步就能实现",
        "真实用户评价",
        "科学验证的效果",
        "限量供应，先到先得",
        "点击了解更多详情"
    ]

    ctas = [
        "立即购买",
        "了解更多",
        "免费试用",
        "马上行动",
        "点击查看",
        "限时抢购"
    ]

    for i in range(n_samples):
        # 随机选择模板
        hook_id = np.random.randint(0, len(hooks))
        body_id = np.random.randint(0, len(bodies))
        cta_id = np.random.randint(0, len(ctas))

        content = {
            'hook': hooks[hook_id],
            'body': bodies[body_id],
            'cta': ctas[cta_id]
        }
        contents.append(content)

        action = {
            'hook_id': hook_id,
            'body_id': body_id,
            'cta_id': cta_id
        }
        actions.append(action)

        # 生成模拟标签（基于一些规则）
        # CTR: 受 hook 影响较大
        base_ctr = 0.05 + (hook_id / len(hooks)) * 0.1
        labels['ctr'].append(np.clip(base_ctr + np.random.normal(0, 0.02), 0, 1))

        # 完播率: 受 body 影响较大
        base_completion = 0.4 + (body_id / len(bodies)) * 0.3
        labels['completion_rate'].append(np.clip(base_completion + np.random.normal(0, 0.05), 0, 1))

        # 互动率: 受 hook 和 body 影响
        base_engagement = 0.1 + (hook_id + body_id) / (len(hooks) + len(bodies)) * 0.2
        labels['engagement_rate'].append(np.clip(base_engagement + np.random.normal(0, 0.03), 0, 1))

        # 转化率: 受 cta 影响较大
        base_conversion = 0.02 + (cta_id / len(ctas)) * 0.05
        labels['conversion_rate'].append(np.clip(base_conversion + np.random.normal(0, 0.01), 0, 1))

    logger.info("✅ 模拟数据生成完成")
    return contents, actions, labels


def train_predictors(
    data_path: str,
    output_dir: str,
    n_estimators: int = 100,
    learning_rate: float = 0.05,
    max_depth: int = 6
):
    """
    训练预测器

    Args:
        data_path: 数据路径
        output_dir: 输出目录
        n_estimators: 树的数量
        learning_rate: 学习率
        max_depth: 最大深度
    """
    logger.info("=" * 60)
    logger.info("开始训练真实指标预测器")
    logger.info("=" * 60)

    # 1. 加载数据
    contents, actions, labels = load_tiktok_data(data_path)

    if len(contents) == 0:
        logger.error("没有数据可用于训练")
        return

    # 2. 创建预测器集成
    ensemble = RealMetricPredictorEnsemble()

    # 3. 训练所有预测器
    logger.info("\n训练参数:")
    logger.info(f"  - n_estimators: {n_estimators}")
    logger.info(f"  - learning_rate: {learning_rate}")
    logger.info(f"  - max_depth: {max_depth}")
    logger.info(f"  - 训练样本数: {len(contents)}")

    ensemble.train_all(
        contents=contents,
        actions=actions,
        labels=labels,
        n_estimators=n_estimators,
        learning_rate=learning_rate,
        max_depth=max_depth
    )

    # 4. 保存模型
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    ensemble.save_all(output_dir)

    logger.info(f"\n✅ 所有预测器已保存到: {output_dir}")

    # 5. 测试预测
    logger.info("\n测试预测:")
    test_content = {
        'hook': '限时优惠！',
        'body': '这个产品改变了我的生活',
        'cta': '立即购买'
    }
    test_action = {
        'hook_id': 0,
        'body_id': 0,
        'cta_id': 0
    }

    predictions = ensemble.predict_all(test_content, test_action)
    logger.info(f"  测试内容: {test_content}")
    logger.info(f"  预测结果:")
    for metric, value in predictions.items():
        logger.info(f"    - {metric}: {value:.4f}")

    logger.info("\n" + "=" * 60)
    logger.info("训练完成！")
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="训练真实指标预测器")

    parser.add_argument(
        '--data-path',
        type=str,
        default='data/tiktok_10m/processed/train.jsonl',
        help='训练数据路径'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        default='models/metric_predictors',
        help='模型输出目录'
    )

    parser.add_argument(
        '--n-estimators',
        type=int,
        default=100,
        help='LightGBM 树的数量'
    )

    parser.add_argument(
        '--learning-rate',
        type=float,
        default=0.05,
        help='学习率'
    )

    parser.add_argument(
        '--max-depth',
        type=int,
        default=6,
        help='树的最大深度'
    )

    args = parser.parse_args()

    train_predictors(
        data_path=args.data_path,
        output_dir=args.output_dir,
        n_estimators=args.n_estimators,
        learning_rate=args.learning_rate,
        max_depth=args.max_depth
    )


if __name__ == '__main__':
    main()
