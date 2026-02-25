"""
HelpSteer3 数据集下载和预处理脚本

功能：
1. 从 Hugging Face 下载 HelpSteer3-Preference 数据集
2. 转换为 DPO 训练所需格式
3. 数据清洗和验证
4. 保存为 JSONL 格式
"""

import os
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

try:
    from datasets import load_dataset
    from tqdm import tqdm
except ImportError:
    print("❌ 缺少依赖库")
    print("请运行: pip install datasets tqdm")
    exit(1)


def download_helpsteer3(
    output_dir: str = "./data/helpsteer3",
    split: str = "train",
    cache_dir: str = None
) -> List[Dict[str, Any]]:
    """下载 HelpSteer3-Preference 数据集

    Args:
        output_dir: 输出目录
        split: 数据集分割（train/validation/test）
        cache_dir: 缓存目录

    Returns:
        数据集列表
    """
    print("="*80)
    print("📥 下载 HelpSteer3-Preference 数据集")
    print("="*80)

    print(f"\n数据集: nvidia/HelpSteer3")
    print(f"分割: {split}")
    print(f"输出目录: {output_dir}")

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    # 下载数据集
    print("\n⏳ 正在下载...")
    try:
        dataset = load_dataset(
            "nvidia/HelpSteer3",
            split=split,
            cache_dir=cache_dir
        )
        print(f"✅ 下载完成！共 {len(dataset)} 条数据")
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        print("\n可能的原因:")
        print("1. 网络连接问题")
        print("2. Hugging Face 访问受限")
        print("\n解决方案:")
        print("1. 使用代理: export HF_ENDPOINT=https://hf-mirror.com")
        print("2. 手动下载: https://huggingface.co/datasets/nvidia/HelpSteer3")
        raise

    return dataset


def convert_to_dpo_format(
    dataset,
    output_path: str,
    max_samples: int = None,
    min_prompt_length: int = 10,
    max_prompt_length: int = 2048,
    min_response_length: int = 10,
    max_response_length: int = 4096
) -> int:
    """转换为 DPO 训练格式

    Args:
        dataset: 原始数据集
        output_path: 输出文件路径
        max_samples: 最大样本数（None 表示全部）
        min_prompt_length: 最小 prompt 长度
        max_prompt_length: 最大 prompt 长度
        min_response_length: 最小响应长度
        max_response_length: 最大响应长度

    Returns:
        有效样本数
    """
    print("\n🔄 转换为 DPO 格式...")

    valid_samples = 0
    skipped_samples = 0

    with open(output_path, 'w', encoding='utf-8') as f:
        for i, item in enumerate(tqdm(dataset, desc="处理数据")):
            # 限制样本数
            if max_samples and valid_samples >= max_samples:
                break

            # 提取字段
            prompt = item.get("prompt", "")
            chosen = item.get("response", "")  # HelpSteer3 使用 response 字段
            rejected = item.get("response_rejected", "")

            # 数据验证
            if not prompt or not chosen:
                skipped_samples += 1
                continue

            # 长度过滤
            if not (min_prompt_length <= len(prompt) <= max_prompt_length):
                skipped_samples += 1
                continue

            if not (min_response_length <= len(chosen) <= max_response_length):
                skipped_samples += 1
                continue

            # 如果没有 rejected，使用低质量的 response
            if not rejected:
                # HelpSteer3 可能没有显式的 rejected，需要从其他样本中选择
                # 这里简化处理：跳过没有 rejected 的样本
                skipped_samples += 1
                continue

            if not (min_response_length <= len(rejected) <= max_response_length):
                skipped_samples += 1
                continue

            # 确保 chosen 和 rejected 不同
            if chosen == rejected:
                skipped_samples += 1
                continue

            # 构建 DPO 格式
            dpo_sample = {
                "prompt": prompt,
                "chosen": chosen,
                "rejected": rejected,
                "source": "helpsteer3",
                "sample_id": f"helpsteer3_{i}"
            }

            # 写入文件
            f.write(json.dumps(dpo_sample, ensure_ascii=False) + '\n')
            valid_samples += 1

    print(f"\n✅ 转换完成！")
    print(f"   有效样本: {valid_samples}")
    print(f"   跳过样本: {skipped_samples}")
    print(f"   输出文件: {output_path}")

    return valid_samples


def split_train_validation(
    input_path: str,
    train_path: str,
    validation_path: str,
    validation_ratio: float = 0.1
):
    """分割训练集和验证集

    Args:
        input_path: 输入文件路径
        train_path: 训练集输出路径
        validation_path: 验证集输出路径
        validation_ratio: 验证集比例
    """
    print(f"\n📊 分割训练集和验证集（验证集比例: {validation_ratio}）...")

    # 读取所有样本
    samples = []
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            samples.append(json.loads(line))

    total = len(samples)
    val_size = int(total * validation_ratio)
    train_size = total - val_size

    print(f"   总样本数: {total}")
    print(f"   训练集: {train_size}")
    print(f"   验证集: {val_size}")

    # 分割
    train_samples = samples[:train_size]
    val_samples = samples[train_size:]

    # 保存训练集
    with open(train_path, 'w', encoding='utf-8') as f:
        for sample in train_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')

    # 保存验证集
    with open(validation_path, 'w', encoding='utf-8') as f:
        for sample in val_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')

    print(f"✅ 分割完成！")
    print(f"   训练集: {train_path}")
    print(f"   验证集: {validation_path}")


def generate_dataset_info(
    output_dir: str,
    train_samples: int,
    val_samples: int
):
    """生成数据集信息文件

    Args:
        output_dir: 输出目录
        train_samples: 训练样本数
        val_samples: 验证样本数
    """
    info = {
        "dataset_name": "HelpSteer3-Preference",
        "source": "nvidia/HelpSteer3",
        "license": "CC-BY-4.0",
        "download_date": datetime.now().isoformat(),
        "train_samples": train_samples,
        "validation_samples": val_samples,
        "total_samples": train_samples + val_samples,
        "format": "DPO (prompt, chosen, rejected)",
        "files": {
            "train": "train.jsonl",
            "validation": "validation.jsonl"
        }
    }

    info_path = os.path.join(output_dir, "dataset_info.json")
    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(info, f, indent=2, ensure_ascii=False)

    print(f"\n📄 数据集信息已保存: {info_path}")


def main():
    parser = argparse.ArgumentParser(description="下载和预处理 HelpSteer3 数据集")

    parser.add_argument(
        "--output-dir",
        type=str,
        default="./data/helpsteer3",
        help="输出目录"
    )
    parser.add_argument(
        "--split",
        type=str,
        default="train",
        choices=["train", "validation", "test"],
        help="数据集分割"
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="最大样本数（用于快速测试）"
    )
    parser.add_argument(
        "--validation-ratio",
        type=float,
        default=0.1,
        help="验证集比例"
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        default=None,
        help="Hugging Face 缓存目录"
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="跳过下载，仅处理已有数据"
    )

    args = parser.parse_args()

    print("="*80)
    print("📦 HelpSteer3 数据集下载和预处理")
    print("="*80)

    # 创建输出目录
    os.makedirs(args.output_dir, exist_ok=True)

    # 下载数据集
    if not args.skip_download:
        dataset = download_helpsteer3(
            output_dir=args.output_dir,
            split=args.split,
            cache_dir=args.cache_dir
        )
    else:
        print("⏭️  跳过下载")
        return

    # 转换为 DPO 格式
    all_samples_path = os.path.join(args.output_dir, "all_samples.jsonl")
    valid_samples = convert_to_dpo_format(
        dataset=dataset,
        output_path=all_samples_path,
        max_samples=args.max_samples
    )

    if valid_samples == 0:
        print("❌ 没有有效样本！")
        return

    # 分割训练集和验证集
    train_path = os.path.join(args.output_dir, "train.jsonl")
    validation_path = os.path.join(args.output_dir, "validation.jsonl")

    split_train_validation(
        input_path=all_samples_path,
        train_path=train_path,
        validation_path=validation_path,
        validation_ratio=args.validation_ratio
    )

    # 计算样本数
    train_samples = sum(1 for _ in open(train_path, 'r', encoding='utf-8'))
    val_samples = sum(1 for _ in open(validation_path, 'r', encoding='utf-8'))

    # 生成数据集信息
    generate_dataset_info(
        output_dir=args.output_dir,
        train_samples=train_samples,
        val_samples=val_samples
    )

    print("\n" + "="*80)
    print("✅ 全部完成！")
    print("="*80)
    print(f"\n数据集位置: {args.output_dir}")
    print(f"训练集: {train_path} ({train_samples} 样本)")
    print(f"验证集: {validation_path} ({val_samples} 样本)")
    print("\n下一步:")
    print(f"python scripts/train_dpo_test.py --train-data {train_path} --val-data {validation_path}")


if __name__ == "__main__":
    main()
