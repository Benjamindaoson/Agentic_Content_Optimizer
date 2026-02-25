#!/usr/bin/env python3
"""
SFT 训练脚本

使用示例:
    python scripts/train_sft.py --config configs/training/sft_example.json
    python scripts/train_sft.py --platform xiaohongshu --adapter-name xhs_test_v1
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
    parser = argparse.ArgumentParser(description="SFT 训练脚本")
    parser.add_argument("--config", type=str, help="配置文件路径")
    parser.add_argument("--platform", type=str, help="平台")
    parser.add_argument("--adapter-name", type=str, help="Adapter 名称")
    parser.add_argument("--base-model", type=str, default="Qwen/Qwen2.5-7B-Instruct", help="基础模型")
    parser.add_argument("--persona", type=str, help="人设")
    parser.add_argument("--niche", type=str, help="领域")
    parser.add_argument("--days", type=int, default=30, help="数据天数")
    parser.add_argument("--max-samples", type=int, help="最大样本数")
    parser.add_argument("--epochs", type=int, default=3, help="训练轮数")
    parser.add_argument("--batch-size", type=int, default=4, help="批次大小")
    parser.add_argument("--lr", type=float, default=2e-4, help="学习率")

    args = parser.parse_args()

    # 加载配置
    if args.config:
        logger.info(f"从配置文件加载: {args.config}")
        with open(args.config, "r", encoding="utf-8") as f:
            config = json.load(f)
    else:
        # 从命令行参数构建配置
        if not args.platform or not args.adapter_name:
            parser.error("必须提供 --config 或 (--platform 和 --adapter-name)")

        config = {
            "platform": args.platform,
            "adapter_name": args.adapter_name,
            "base_model": args.base_model,
            "persona": args.persona,
            "niche": args.niche,
            "days": args.days,
            "max_samples": args.max_samples,
            "num_train_epochs": args.epochs,
            "per_device_train_batch_size": args.batch_size,
            "learning_rate": args.lr,
        }

    logger.info("=" * 80)
    logger.info("SFT 训练配置:")
    logger.info(json.dumps(config, indent=2, ensure_ascii=False))
    logger.info("=" * 80)

    # 创建数据库会话
    db = SessionLocal()

    try:
        # 创建训练服务
        service = TrainingService(db)

        # 开始训练
        logger.info("开始 SFT 训练...")
        result = service.train_sft(**config)

        logger.info("=" * 80)
        logger.info("SFT 训练完成!")
        logger.info(json.dumps(result, indent=2, ensure_ascii=False))
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"训练失败: {e}", exc_info=True)
        sys.exit(1)

    finally:
        db.close()


if __name__ == "__main__":
    main()
