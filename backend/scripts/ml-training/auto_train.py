#!/usr/bin/env python3
"""
自动训练流水线脚本

使用示例:
    python scripts/auto_train.py --config configs/training/auto_training_example.json
    python scripts/auto_train.py --platform xiaohongshu --persona 学生党 --niche AI工具
"""

import sys
from pathlib import Path
import argparse
import json
import logging

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.database import SessionLocal
from app.ml.services.training_service import TrainingService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="自动训练流水线脚本")
    parser.add_argument("--config", type=str, help="配置文件路径")
    parser.add_argument("--platform", type=str, help="平台")
    parser.add_argument("--persona", type=str, help="人设")
    parser.add_argument("--niche", type=str, help="领域")
    parser.add_argument("--sft-days", type=int, default=30, help="SFT 数据天数")
    parser.add_argument("--dpo-days", type=int, default=30, help="DPO 数据天数")

    args = parser.parse_args()

    # 加载配置
    if args.config:
        logger.info(f"从配置文件加载: {args.config}")
        with open(args.config, "r", encoding="utf-8") as f:
            config = json.load(f)
    else:
        # 从命令行参数构建配置
        if not args.platform or not args.persona or not args.niche:
            parser.error("必须提供 --config 或 (--platform, --persona 和 --niche)")

        config = {
            "platform": args.platform,
            "persona": args.persona,
            "niche": args.niche,
            "sft_days": args.sft_days,
            "dpo_days": args.dpo_days,
        }

    logger.info("=" * 80)
    logger.info("自动训练流水线配置:")
    logger.info(json.dumps(config, indent=2, ensure_ascii=False))
    logger.info("=" * 80)

    # 创建数据库会话
    db = SessionLocal()

    try:
        # 创建训练服务
        service = TrainingService(db)

        # 开始自动训练
        logger.info("开始自动训练流水线 (SFT -> DPO)...")
        result = service.auto_train_pipeline(**config)

        logger.info("=" * 80)
        logger.info("自动训练流水线完成!")
        logger.info(json.dumps(result, indent=2, ensure_ascii=False))
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"训练失败: {e}", exc_info=True)
        sys.exit(1)

    finally:
        db.close()


if __name__ == "__main__":
    main()
