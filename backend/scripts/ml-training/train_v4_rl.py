#!/usr/bin/env python3
"""
v4.0 RL 一键训练脚本

训练所有强化学习组件
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import get_db
from app.growth_brain.auto_account_manager_rl import AutoAccountManagerRL
from app.growth_brain.multimodal_cover_engine_rl import MultimodalCoverEngineRL
from app.growth_brain.multi_platform_engine_rl import MultiPlatformEngineRL
from app.growth_brain.causal_inference_engine_rl import CausalInferenceEngineRL


async def train_all(days: int = 7):
    """训练所有 RL 组件"""
    print("=" * 60)
    print("Growth Flywheel v4.0 - RL 训练")
    print("=" * 60)
    print()

    db = next(get_db())

    results = {}

    # 1. 训练账号运营策略
    print("1. 训练账号运营策略...")
    try:
        account_rl = AutoAccountManagerRL(db)
        result = await account_rl.train_policy(days=days)
        results['account'] = result
        print(f"   ✓ 完成: {result['total_samples']} 样本, "
              f"提升 {result['avg_improvement']:.2%}")
    except Exception as e:
        print(f"   ✗ 失败: {e}")
        results['account'] = {'status': 'error', 'error': str(e)}

    print()

    # 2. 训练封面生成策略
    print("2. 训练封面生成策略...")
    try:
        cover_rl = MultimodalCoverEngineRL(db)
        result = await cover_rl.train_cover_policy(days=days)
        results['cover'] = result
        print(f"   ✓ 完成: {result.total_samples} 样本")
    except Exception as e:
        print(f"   ✗ 失败: {e}")
        results['cover'] = {'status': 'error', 'error': str(e)}

    print()

    # 3. 训练平台选择策略
    print("3. 训练平台选择策略...")
    try:
        platform_rl = MultiPlatformEngineRL(db)
        result = await platform_rl.train_platform_policy(days=days)
        results['platform'] = result
        print(f"   ✓ 完成: {result.total_samples} 样本")
    except Exception as e:
        print(f"   ✗ 失败: {e}")
        results['platform'] = {'status': 'error', 'error': str(e)}

    print()

    # 4. 评估准确性
    print("4. 评估预测准确性...")
    try:
        account_rl = AutoAccountManagerRL(db)
        eval_report = await account_rl.evaluate_accuracy(days=days)

        if eval_report['status'] == 'success':
            metrics = eval_report['metrics']
            print(f"   ✓ MAE: {metrics['mae']:.3f}")
            print(f"   ✓ RMSE: {metrics['rmse']:.3f}")
            print(f"   ✓ MAPE: {metrics['mape']:.1f}%")
            print(f"   ✓ 准确率: {metrics['accuracy_rate']:.1%}")
        else:
            print(f"   ⚠ 无数据")
    except Exception as e:
        print(f"   ✗ 失败: {e}")

    print()
    print("=" * 60)
    print("训练完成!")
    print("=" * 60)

    return results


async def train_single(component: str, days: int = 7):
    """训练单个组件"""
    db = next(get_db())

    if component == 'account':
        print("训练账号运营策略...")
        rl = AutoAccountManagerRL(db)
        result = await rl.train_policy(days=days)
        print(f"✓ 完成: {result}")
        return result

    elif component == 'cover':
        print("训练封面生成策略...")
        rl = MultimodalCoverEngineRL(db)
        result = await rl.train_cover_policy(days=days)
        print(f"✓ 完成: {result}")
        return result

    elif component == 'platform':
        print("训练平台选择策略...")
        rl = MultiPlatformEngineRL(db)
        result = await rl.train_platform_policy(days=days)
        print(f"✓ 完成: {result}")
        return result

    else:
        print(f"✗ 未知组件: {component}")
        print("可用组件: account, cover, platform")
        return None


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='v4.0 RL 训练脚本')
    parser.add_argument(
        '--component',
        type=str,
        choices=['all', 'account', 'cover', 'platform'],
        default='all',
        help='训练组件 (默认: all)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='训练数据时间窗口（天）'
    )

    args = parser.parse_args()

    if args.component == 'all':
        asyncio.run(train_all(days=args.days))
    else:
        asyncio.run(train_single(args.component, days=args.days))


if __name__ == '__main__':
    main()
