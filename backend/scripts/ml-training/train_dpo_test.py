"""
DPO 训练测试脚本

功能：
1. 使用 HelpSteer3 数据集进行第一次 DPO 训练测试
2. 验证训练流程是否正常
3. 生成训练报告
"""

import os
import sys
import argparse
import json
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from app.training import DPOTrainer, DPOConfig
    from app.training.model_manager import ModelManager
    from app.data_engineering.synthetic_data_generator import PreferencePair
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("请确保在 backend 目录下运行此脚本")
    sys.exit(1)


def load_jsonl_dataset(file_path: str, max_samples: int = None):
    """加载 JSONL 格式的数据集

    Args:
        file_path: 文件路径
        max_samples: 最大样本数

    Returns:
        PreferencePair 列表
    """
    print(f"📂 加载数据集: {file_path}")

    pairs = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if max_samples and i >= max_samples:
                break

            data = json.loads(line)
            pair = PreferencePair(
                pair_id=data.get("sample_id", f"sample_{i}"),
                topic=data.get("prompt", ""),
                platform="general",
                chosen_content=data.get("chosen", ""),
                rejected_content=data.get("rejected", ""),
                chosen_score=10.0,  # HelpSteer3 没有显式分数
                rejected_score=5.0,
                metadata={
                    "source": data.get("source", "helpsteer3")
                }
            )
            pairs.append(pair)

    print(f"✅ 加载完成: {len(pairs)} 个偏好对")
    return pairs


def run_training_test(
    train_data_path: str,
    val_data_path: str,
    model_name: str = "rednote-hilab/dots.llm1.inst",
    output_dir: str = "./training_output",
    max_train_samples: int = 100,
    max_val_samples: int = 20,
    num_epochs: int = 1,
    batch_size: int = 2,
    learning_rate: float = 5e-6,
    use_lora: bool = True,
    lora_r: int = 8,
    test_mode: bool = True
):
    """运行 DPO 训练测试

    Args:
        train_data_path: 训练数据路径
        val_data_path: 验证数据路径
        model_name: 模型名称
        output_dir: 输出目录
        max_train_samples: 最大训练样本数（测试模式）
        max_val_samples: 最大验证样本数（测试模式）
        num_epochs: 训练轮数
        batch_size: 批次大小
        learning_rate: 学习率
        use_lora: 是否使用 LoRA
        lora_r: LoRA 秩
        test_mode: 测试模式（使用少量数据快速验证）
    """
    print("="*80)
    print("🚀 DPO 训练测试")
    print("="*80)

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    # 加载数据集
    print("\n📊 加载数据集...")
    train_pairs = load_jsonl_dataset(
        train_data_path,
        max_samples=max_train_samples if test_mode else None
    )
    val_pairs = load_jsonl_dataset(
        val_data_path,
        max_samples=max_val_samples if test_mode else None
    )

    if len(train_pairs) == 0:
        print("❌ 训练集为空！")
        return

    print(f"\n训练集: {len(train_pairs)} 样本")
    print(f"验证集: {len(val_pairs)} 样本")

    # 配置 DPO 训练器
    print("\n⚙️  配置训练器...")
    config = DPOConfig(
        model_name=model_name,
        output_dir=output_dir,
        num_epochs=num_epochs,
        batch_size=batch_size,
        learning_rate=learning_rate,
        use_lora=use_lora,
        lora_r=lora_r,
        lora_alpha=lora_r * 4,
        max_length=1024,
        beta=0.1,
        logging_steps=5,
        save_steps=50,
        eval_steps=50
    )

    print(f"   模型: {model_name}")
    print(f"   LoRA: {use_lora} (r={lora_r})")
    print(f"   训练轮数: {num_epochs}")
    print(f"   批次大小: {batch_size}")
    print(f"   学习率: {learning_rate}")
    print(f"   Beta: {config.beta}")

    # 创建训练器
    print("\n🔧 初始化训练器...")
    try:
        trainer = DPOTrainer(config=config)
        print("✅ 训练器初始化成功")
    except Exception as e:
        print(f"❌ 训练器初始化失败: {e}")
        print("\n可能的原因:")
        print("1. 模型路径不正确")
        print("2. GPU 显存不足")
        print("3. 依赖库未安装")
        return

    # 加载模型
    print("\n📦 加载模型...")
    try:
        trainer.load_model()
        print("✅ 模型加载成功")
    except Exception as e:
        print(f"❌ 模型加载失败: {e}")
        print("\n请确保:")
        print(f"1. 模型已下载: {model_name}")
        print("2. 有足够的 GPU 显存")
        return

    # 开始训练
    print("\n🎯 开始训练...")
    print("="*80)

    start_time = datetime.now()

    try:
        result = trainer.train(
            preference_pairs=train_pairs,
            validation_pairs=val_pairs
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        print("\n" + "="*80)
        print("✅ 训练完成！")
        print("="*80)

        print(f"\n训练时间: {duration:.1f} 秒")
        print(f"模型保存位置: {result['model_path']}")

        # 生成训练报告
        report = {
            "status": "success",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "config": {
                "model_name": model_name,
                "num_epochs": num_epochs,
                "batch_size": batch_size,
                "learning_rate": learning_rate,
                "use_lora": use_lora,
                "lora_r": lora_r
            },
            "data": {
                "train_samples": len(train_pairs),
                "val_samples": len(val_pairs)
            },
            "result": result
        }

        report_path = os.path.join(output_dir, "training_report.json")
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n📄 训练报告已保存: {report_path}")

        # 注册模型
        print("\n📝 注册模型...")
        model_manager = ModelManager()
        version_id = model_manager.register_model(
            model_path=result['model_path'],
            base_model=model_name,
            training_method="dpo",
            metrics={
                "train_loss": result.get('train_loss', 0.0),
                "eval_loss": result.get('eval_loss', 0.0)
            },
            metadata={
                "training_date": datetime.now().isoformat(),
                "train_samples": len(train_pairs),
                "val_samples": len(val_pairs),
                "test_mode": test_mode
            }
        )

        print(f"✅ 模型已注册: {version_id}")

        print("\n" + "="*80)
        print("🎉 测试成功！")
        print("="*80)
        print("\n下一步:")
        print("1. 查看训练日志: tensorboard --logdir=" + output_dir)
        print("2. 使用完整数据集训练:")
        print(f"   python {__file__} --train-data {train_data_path} --val-data {val_data_path} --no-test-mode")
        print("3. 激活模型:")
        print(f"   curl -X POST http://localhost:8000/api/finetune/models/{version_id}/activate")

    except Exception as e:
        print(f"\n❌ 训练失败: {e}")
        print("\n错误详情:")
        import traceback
        traceback.print_exc()

        # 生成错误报告
        error_report = {
            "status": "failed",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "timestamp": datetime.now().isoformat()
        }

        error_report_path = os.path.join(output_dir, "error_report.json")
        with open(error_report_path, 'w', encoding='utf-8') as f:
            json.dump(error_report, f, indent=2, ensure_ascii=False)

        print(f"\n错误报告已保存: {error_report_path}")


def main():
    parser = argparse.ArgumentParser(description="DPO 训练测试脚本")

    parser.add_argument(
        "--train-data",
        type=str,
        required=True,
        help="训练数据路径（JSONL 格式）"
    )
    parser.add_argument(
        "--val-data",
        type=str,
        required=True,
        help="验证数据路径（JSONL 格式）"
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="rednote-hilab/dots.llm1.inst",
        help="模型名称或路径"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./training_output",
        help="输出目录"
    )
    parser.add_argument(
        "--max-train-samples",
        type=int,
        default=100,
        help="最大训练样本数（测试模式）"
    )
    parser.add_argument(
        "--max-val-samples",
        type=int,
        default=20,
        help="最大验证样本数（测试模式）"
    )
    parser.add_argument(
        "--num-epochs",
        type=int,
        default=1,
        help="训练轮数"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=2,
        help="批次大小"
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=5e-6,
        help="学习率"
    )
    parser.add_argument(
        "--lora-r",
        type=int,
        default=8,
        help="LoRA 秩"
    )
    parser.add_argument(
        "--no-lora",
        action="store_true",
        help="不使用 LoRA"
    )
    parser.add_argument(
        "--no-test-mode",
        action="store_true",
        help="使用完整数据集（非测试模式）"
    )

    args = parser.parse_args()

    # 检查文件是否存在
    if not os.path.exists(args.train_data):
        print(f"❌ 训练数据不存在: {args.train_data}")
        print("\n请先下载数据集:")
        print("python scripts/download_helpsteer3.py")
        sys.exit(1)

    if not os.path.exists(args.val_data):
        print(f"❌ 验证数据不存在: {args.val_data}")
        sys.exit(1)

    # 运行训练测试
    run_training_test(
        train_data_path=args.train_data,
        val_data_path=args.val_data,
        model_name=args.model_name,
        output_dir=args.output_dir,
        max_train_samples=args.max_train_samples,
        max_val_samples=args.max_val_samples,
        num_epochs=args.num_epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        use_lora=not args.no_lora,
        lora_r=args.lora_r,
        test_mode=not args.no_test_mode
    )


if __name__ == "__main__":
    main()
