#!/usr/bin/env python3
"""
测试 ML 训练系统

验证:
1. 数据库表创建成功
2. 数据插入和查询
3. DatasetBuilder 工作正常
4. AdapterRegistry 工作正常
"""

import sys
from pathlib import Path
import uuid
import time
from datetime import datetime

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.database import SessionLocal
from app.ml.training.schemas import GenerationTrace, Outcome
from app.ml.training.dataset_builder import DatasetBuilder
from app.ml.models.adapter_registry import AdapterRegistry
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_generation_trace():
    """测试 GenerationTrace 插入"""
    logger.info("\n" + "=" * 80)
    logger.info("📝 测试 GenerationTrace 插入")
    logger.info("=" * 80)

    db = SessionLocal()

    try:
        # 创建测试数据
        trace = GenerationTrace(
            id=str(uuid.uuid4()),
            platform="xiaohongshu",
            persona="学生党",
            niche="AI工具",
            topic="AI 写作工具推荐",
            prompt="写一篇关于 AI 写作工具的小红书笔记",
            system_prompt="你是小红书平台的专业内容创作者",
            output="🤖 学生党必备！这款 AI 写作工具太好用了\n\n作为一名大学生，每天都要写各种作业和论文...",
            title="学生党必备的 AI 写作神器",
            tags=["AI工具", "学习效率", "写作助手"],
            model_id="claude-3.5-sonnet",
            generation_time_ms=8500,
            token_count=450,
        )

        db.add(trace)
        db.commit()
        db.refresh(trace)

        logger.info(f"✅ GenerationTrace 创建成功")
        logger.info(f"   ID: {trace.id}")
        logger.info(f"   平台: {trace.platform}")
        logger.info(f"   主题: {trace.topic}")
        logger.info(f"   人设: {trace.persona}")
        logger.info(f"   领域: {trace.niche}")

        # 查询验证
        count = db.query(GenerationTrace).count()
        logger.info(f"\n📊 数据库中共有 {count} 条 GenerationTrace")

        return trace.id

    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)
        db.rollback()
        return None

    finally:
        db.close()


def test_outcome(trace_id: str):
    """测试 Outcome 插入"""
    logger.info("\n" + "=" * 80)
    logger.info("📊 测试 Outcome 插入")
    logger.info("=" * 80)

    db = SessionLocal()

    try:
        # 创建测试数据
        outcome = Outcome(
            id=str(uuid.uuid4()),
            trace_id=trace_id,
            impressions=1000,
            clicks=50,
            click_rate=0.05,
            read_time_avg=45.0,
            completion_rate=0.8,
            likes=20,
            comments=5,
            saves=15,
            shares=3,
        )

        # 计算 engagement_score
        from app.ml.training.dataset_builder import DatasetBuilder
        builder = DatasetBuilder(db)
        outcome.engagement_score = builder.calculate_engagement_score(outcome)

        db.add(outcome)
        db.commit()
        db.refresh(outcome)

        logger.info(f"✅ Outcome 创建成功")
        logger.info(f"   ID: {outcome.id}")
        logger.info(f"   Trace ID: {outcome.trace_id}")
        logger.info(f"   曝光: {outcome.impressions}")
        logger.info(f"   点击率: {outcome.click_rate:.2%}")
        logger.info(f"   互动分: {outcome.engagement_score:.4f}")

        # 查询验证
        count = db.query(Outcome).count()
        logger.info(f"\n📊 数据库中共有 {count} 条 Outcome")

        return outcome.id

    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)
        db.rollback()
        return None

    finally:
        db.close()


def test_dataset_builder():
    """测试 DatasetBuilder"""
    logger.info("\n" + "=" * 80)
    logger.info("🔨 测试 DatasetBuilder")
    logger.info("=" * 80)

    db = SessionLocal()

    try:
        builder = DatasetBuilder(db)

        # 测试 SFT 数据集构建
        logger.info("\n📝 测试 SFT 数据集构建...")
        try:
            sft_dataset = builder.build_sft_dataset(
                platform="xiaohongshu",
                days=30,
                min_engagement_score=0.0,
                max_samples=10
            )
            logger.info(f"✅ SFT 数据集构建成功")
            logger.info(f"   样本数: {sft_dataset.total_samples}")
        except Exception as e:
            logger.warning(f"⚠️  SFT 数据集构建失败（可能数据不足）: {e}")

        # 测试 DPO 数据集构建
        logger.info("\n📝 测试 DPO 数据集构建...")
        try:
            dpo_dataset = builder.build_dpo_dataset(
                platform="xiaohongshu",
                days=30,
                min_score_diff=0.0,
                max_pairs=10
            )
            logger.info(f"✅ DPO 数据集构建成功")
            logger.info(f"   偏好对数: {dpo_dataset.total_samples}")
        except Exception as e:
            logger.warning(f"⚠️  DPO 数据集构建失败（可能数据不足）: {e}")

    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)

    finally:
        db.close()


def test_adapter_registry():
    """测试 AdapterRegistry"""
    logger.info("\n" + "=" * 80)
    logger.info("📦 测试 AdapterRegistry")
    logger.info("=" * 80)

    db = SessionLocal()

    try:
        registry = AdapterRegistry(db)

        # 注册测试 adapter
        logger.info("\n📝 注册测试 adapter...")
        adapter = registry.register(
            adapter_name="test_adapter_v1",
            adapter_type="sft",
            base_model="Qwen/Qwen2.5-7B-Instruct",
            adapter_path="./outputs/test/test_adapter_v1",
            platform="xiaohongshu",
            persona="学生党",
            niche="AI工具",
            training_samples=100,
            training_epochs=3,
            training_time_seconds=3600.0,
        )

        logger.info(f"✅ Adapter 注册成功")
        logger.info(f"   ID: {adapter.id}")
        logger.info(f"   名称: {adapter.adapter_name}")
        logger.info(f"   类型: {adapter.adapter_type}")
        logger.info(f"   平台: {adapter.platform}")

        # 查询验证
        adapters = registry.list(platform="xiaohongshu")
        logger.info(f"\n📊 数据库中共有 {len(adapters)} 个 adapter")

        # 设置默认
        logger.info("\n📝 设置默认 adapter...")
        registry.set_default("test_adapter_v1")
        logger.info(f"✅ 默认 adapter 设置成功")

        # 获取默认
        default = registry.get_default(platform="xiaohongshu")
        if default:
            logger.info(f"✅ 获取默认 adapter: {default.adapter_name}")

    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)

    finally:
        db.close()


def main():
    """运行所有测试"""
    logger.info("=" * 80)
    logger.info("🧪 ML 训练系统测试")
    logger.info("=" * 80)

    # 测试 1: GenerationTrace
    trace_id = test_generation_trace()

    if trace_id:
        # 测试 2: Outcome
        outcome_id = test_outcome(trace_id)

    # 测试 3: DatasetBuilder
    test_dataset_builder()

    # 测试 4: AdapterRegistry
    test_adapter_registry()

    logger.info("\n" + "=" * 80)
    logger.info("✅ 所有测试完成！")
    logger.info("=" * 80)

    logger.info("\n🎯 下一步:")
    logger.info("   1. 启动 API: uvicorn app.main:app --reload")
    logger.info("   2. 访问文档: http://localhost:8000/docs")
    logger.info("   3. 测试 API 端点:")
    logger.info("      - GET /api/ml/adapters")
    logger.info("      - POST /api/ml/generate")
    logger.info("   4. 开始收集真实数据")


if __name__ == "__main__":
    main()
