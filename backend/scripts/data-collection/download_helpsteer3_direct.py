"""
直接从 Hugging Face API 下载 HelpSteer3-Preference 数据集

使用 Hugging Face Datasets Server API 直接下载，无需完整的 datasets 库
"""

import os
import json
import time
import requests
from typing import List, Dict, Any
from pathlib import Path
from tqdm import tqdm

# Hugging Face Datasets Server API
API_BASE = "https://datasets-server.huggingface.co"
DATASET_NAME = "nvidia/HelpSteer3"
CONFIG = "preference"
SPLIT = "train"


def fetch_rows(offset: int = 0, length: int = 100) -> Dict[str, Any]:
    """从 Hugging Face API 获取数据行

    Args:
        offset: 起始位置
        length: 获取数量

    Returns:
        API 响应数据
    """
    url = f"{API_BASE}/rows"
    params = {
        "dataset": DATASET_NAME,
        "config": CONFIG,
        "split": SPLIT,
        "offset": offset,
        "length": length
    }

    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


def download_helpsteer3(
    output_dir: str = "./data/helpsteer3",
    max_samples: int = None,
    batch_size: int = 100
) -> int:
    """下载 HelpSteer3 数据集

    Args:
        output_dir: 输出目录
        max_samples: 最大样本数（None 表示全部）
        batch_size: 每次请求的数量

    Returns:
        下载的样本数
    """
    print("="*80)
    print("📥 从 Hugging Face API 下载 HelpSteer3-Preference 数据集")
    print("="*80)

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    # 输出文件
    output_file = os.path.join(output_dir, "all_samples.jsonl")

    # 首先获取数据集信息
    print("\n🔍 获取数据集信息...")
    try:
        first_batch = fetch_rows(offset=0, length=1)
        total_rows = first_batch.get("num_rows_total", 0)
        print(f"✅ 数据集总行数: {total_rows}")
    except Exception as e:
        print(f"❌ 获取数据集信息失败: {e}")
        return 0

    # 确定下载数量
    if max_samples:
        total_to_download = min(max_samples, total_rows)
    else:
        total_to_download = total_rows

    print(f"📊 将下载 {total_to_download} 条数据")

    # 开始下载
    downloaded = 0
    valid_samples = 0
    skipped_samples = 0

    with open(output_file, 'w', encoding='utf-8') as f:
        with tqdm(total=total_to_download, desc="下载进度") as pbar:
            while downloaded < total_to_download:
                # 计算本次请求的数量
                current_batch_size = min(batch_size, total_to_download - downloaded)

                try:
                    # 请求数据
                    data = fetch_rows(offset=downloaded, length=current_batch_size)

                    # 添加延迟，避免触发 API 限流
                    time.sleep(0.5)

                    rows = data.get("rows", [])

                    if not rows:
                        print(f"\n⚠️  偏移 {downloaded} 处没有更多数据")
                        break

                    # 处理每一行
                    for row in rows:
                        row_data = row.get("row", {})

                        # 提取字段
                        prompt = row_data.get("prompt", "")
                        response = row_data.get("response", "")
                        response_rejected = row_data.get("response_rejected", "")

                        # 数据验证
                        if not prompt or not response:
                            skipped_samples += 1
                            continue

                        # 如果没有 rejected，跳过
                        if not response_rejected:
                            skipped_samples += 1
                            continue

                        # 确保 chosen 和 rejected 不同
                        if response == response_rejected:
                            skipped_samples += 1
                            continue

                        # 长度过滤
                        if len(prompt) < 10 or len(prompt) > 2048:
                            skipped_samples += 1
                            continue

                        if len(response) < 10 or len(response) > 4096:
                            skipped_samples += 1
                            continue

                        if len(response_rejected) < 10 or len(response_rejected) > 4096:
                            skipped_samples += 1
                            continue

                        # 构建 DPO 格式
                        dpo_sample = {
                            "prompt": prompt,
                            "chosen": response,
                            "rejected": response_rejected,
                            "source": "helpsteer3",
                            "sample_id": f"helpsteer3_{valid_samples}"
                        }

                        # 写入文件
                        f.write(json.dumps(dpo_sample, ensure_ascii=False) + '\n')
                        valid_samples += 1

                    downloaded += len(rows)
                    pbar.update(len(rows))

                except requests.exceptions.HTTPError as e:
                    # 检查是否是 429 限流错误
                    if hasattr(e, 'response') and e.response is not None and e.response.status_code == 429:
                        print(f"\n⚠️  遇到 API 限流（429），暂停 10 秒后重试...")
                        time.sleep(10)
                        continue  # 重试当前批次
                    else:
                        print(f"\n❌ 下载失败（偏移 {downloaded}）: {e}")
                        break
                except Exception as e:
                    print(f"\n❌ 下载失败（偏移 {downloaded}）: {e}")
                    break

    print(f"\n✅ 下载完成！")
    print(f"   总下载: {downloaded} 条")
    print(f"   有效样本: {valid_samples} 条")
    print(f"   跳过样本: {skipped_samples} 条")
    print(f"   输出文件: {output_file}")

    return valid_samples


def split_train_validation(
    input_file: str,
    output_dir: str,
    validation_ratio: float = 0.1
):
    """分割训练集和验证集

    Args:
        input_file: 输入文件
        output_dir: 输出目录
        validation_ratio: 验证集比例
    """
    print(f"\n📊 分割训练集和验证集（验证集比例: {validation_ratio}）...")

    # 读取所有样本
    samples = []
    with open(input_file, 'r', encoding='utf-8') as f:
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
    train_path = os.path.join(output_dir, "train.jsonl")
    with open(train_path, 'w', encoding='utf-8') as f:
        for sample in train_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')

    # 保存验证集
    val_path = os.path.join(output_dir, "validation.jsonl")
    with open(val_path, 'w', encoding='utf-8') as f:
        for sample in val_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')

    print(f"✅ 分割完成！")
    print(f"   训练集: {train_path}")
    print(f"   验证集: {val_path}")

    return train_path, val_path


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
    from datetime import datetime

    info = {
        "dataset_name": "HelpSteer3-Preference",
        "source": "nvidia/HelpSteer3",
        "license": "CC-BY-4.0",
        "download_date": datetime.now().isoformat(),
        "download_method": "Hugging Face Datasets Server API",
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
    import argparse

    parser = argparse.ArgumentParser(description="从 Hugging Face API 下载 HelpSteer3 数据集")

    parser.add_argument(
        "--output-dir",
        type=str,
        default="./data/helpsteer3",
        help="输出目录"
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="最大样本数（用于快速测试）"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="每次请求的数量"
    )
    parser.add_argument(
        "--validation-ratio",
        type=float,
        default=0.1,
        help="验证集比例"
    )

    args = parser.parse_args()

    print("="*80)
    print("📦 HelpSteer3 数据集下载工具（直接 API 版本）")
    print("="*80)

    # 下载数据集
    valid_samples = download_helpsteer3(
        output_dir=args.output_dir,
        max_samples=args.max_samples,
        batch_size=args.batch_size
    )

    if valid_samples == 0:
        print("❌ 没有有效样本！")
        return

    # 分割训练集和验证集
    all_samples_path = os.path.join(args.output_dir, "all_samples.jsonl")
    train_path, val_path = split_train_validation(
        input_file=all_samples_path,
        output_dir=args.output_dir,
        validation_ratio=args.validation_ratio
    )

    # 计算样本数
    train_samples = sum(1 for _ in open(train_path, 'r', encoding='utf-8'))
    val_samples = sum(1 for _ in open(val_path, 'r', encoding='utf-8'))

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
    print(f"验证集: {val_path} ({val_samples} 样本)")
    print("\n下一步:")
    print(f"python scripts/train_dpo_test.py --train-data {train_path} --val-data {val_path}")


if __name__ == "__main__":
    main()
