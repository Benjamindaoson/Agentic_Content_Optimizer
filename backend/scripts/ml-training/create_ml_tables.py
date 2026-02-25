#!/usr/bin/env python3
"""
创建 ML 训练系统数据库表

包括:
- generation_traces (内容生成记录)
- outcomes (效果数据)
- adapter_registry (Adapter 注册表)
"""

import sys
from pathlib import Path
import asyncio

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.database import engine
from app.ml.training.schemas import Base as MLBase
from app.ml.models.adapter_registry import Base as AdapterBase
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_tables():
    """创建所有 ML 训练相关表"""
    logger.info("=" * 80)
    logger.info("📊 创建 ML 训练系统数据库表")
    logger.info("=" * 80)

    try:
        # 创建 ML 训练表 (generation_traces, outcomes)
        logger.info("\n🔄 创建 ML 训练表...")
        async with engine.begin() as conn:
            await conn.run_sync(MLBase.metadata.create_all)
        logger.info("✅ generation_traces 表创建成功")
        logger.info("✅ outcomes 表创建成功")

        # 创建 Adapter 注册表
        logger.info("\n🔄 创建 Adapter 注册表...")
        async with engine.begin() as conn:
            await conn.run_sync(AdapterBase.metadata.create_all)
        logger.info("✅ adapter_registry 表创建成功")

        logger.info("\n" + "=" * 80)
        logger.info("✅ 所有表创建成功！")
        logger.info("=" * 80)

        logger.info("\n📋 已创建的表:")
        logger.info("   - generation_traces (内容生成记录)")
        logger.info("   - outcomes (效果数据)")
        logger.info("   - adapter_registry (Adapter 注册表)")

        logger.info("\n🎯 下一步:")
        logger.info("   1. 运行测试: python scripts/test_ml_system.py")
        logger.info("   2. 启动 API: uvicorn app.main:app --reload")
        logger.info("   3. 访问文档: http://localhost:8000/docs")

    except Exception as e:
        logger.error(f"\n❌ 创建表失败: {e}", exc_info=True)
        sys.exit(1)


def main():
    asyncio.run(create_tables())


if __name__ == "__main__":
    main()
