"""
使用 Hugging Face datasets 库下载 HelpSteer3-Preference 数据集

相比直接 API 调用，datasets 库提供：
- 自动重试和错误处理
- 断点续传
- 本地缓存
- 更稳定的下载体验
"""

import os
import json
from datasets import load_dataset
from tqdm import tqdm


def convert_to_dpo_format(example):
    """将原始数据集条目转换为 DPO 所需的 (prompt, chosen, rejected) 格式

    HelpSteer3 preference 的真实结构：
    - prompt: 用户问题
    - response_1: 第一个回答
    - response_2: 第二个回答
    - score: 偏好分数（>0 表示 response_1 更好，<0 表示 response_2 更好，=0 表示无偏好）

    Args:
        example: HelpSteer3 数据集的一条记录

    Returns:
        转换后的 DPO 格式字典，如果无法转换则返回 None
    """
    # 提取 prompt
    prompt = example.get('prompt', '')
    if not prompt:
        return None

    # 提取两个回答（注意字段名是 response_1 和 response_2，不是 response_a/b）
    r1 = example.get('response_1', '')
    r2 = example.get('response_2', '')

    # 数据验证
    if not r1 or not r2:
        return None

    # 确保两个回答不同
    if r1 == r2:
        return None

    # 提取偏好分数
    score = example.get('score')

    # 无偏好或分数为 0 的样本跳过
    if score is None or score == 0:
        return None

    # 根据分数选择 chosen 和 rejected
    # score > 0: response_1 更好
    # score < 0: response_2 更好
    if score > 0:
        chosen = r1
        rejected = r2
    else:
        chosen = r2
        rejected = r1

    # 长度过滤
    if len(prompt) < 10 or len(prompt) > 2048:
        return None

    if len(chosen) < 10 or len(chosen) > 4096:
        return None

    if len(rejected) < 10 or len(rejected) > 4096:
        return None

    return {
        "prompt": prompt.strip(),
        "chosen": chosen.strip(),
        "rejected": rejected.strip(),
        "source": "helpsteer3",
        "score": abs(score)  # 保存偏好强度，可用于后续分析
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="使用 datasets 库下载 HelpSteer3 数据集")

    parser.add_argument(
        "--output-dir",
        type=str,
        default="./data/helpsteer3",
        help="输出目录"
    )
    parser.add_argument(
        "--validation-ratio",
        type=float,
        default=0.1,
        help="验证集比例"
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="最大样本数（用于快速测试）"
    )

    args = parser.parse_args()

    print("="*80)
    print("📦 使用 datasets 库下载 HelpSteer3-Preference 数据集")
    print("="*80)

    # 创建输出目录
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    print("\n📥 加载数据集...")
    print("提示：首次下载会缓存到 ~/.cache/huggingface/datasets")

    try:
        # 加载数据集（会自动缓存，支持断点续传）
        ds = load_dataset(
            "nvidia/HelpSteer3",
            "preference",
            split="train"
        )

        print(f"✅ 数据集加载成功！总条数: {len(ds)}")

        # 打印第一条数据的字段，帮助验证数据结构
        if len(ds) > 0:
            print("\n📋 数据集字段预览（第一条）:")
            first_example = ds[0]
            for key in list(first_example.keys())[:10]:  # 只显示前10个字段
                value = first_example[key]
                if isinstance(value, str) and len(value) > 100:
                    value = value[:100] + "..."
                print(f"   {key}: {value}")
            if len(first_example.keys()) > 10:
                print(f"   ... 还有 {len(first_example.keys()) - 10} 个字段")

    except Exception as e:
        print(f"❌ 数据集加载失败: {e}")
        print("\n💡 提示：如果下载速度慢，可以尝试设置镜像：")
        print("   $env:HF_ENDPOINT = \"https://hf-mirror.com\"")
        return

    # 确定处理数量
    total_to_process = len(ds)
    if args.max_samples:
        total_to_process = min(args.max_samples, len(ds))
        print(f"📊 将处理前 {total_to_process} 条数据（测试模式）")

    # 转换数据
    print("\n🔄 转换数据格式...")
    all_samples = []
    skipped = 0

    for idx in tqdm(range(total_to_process), desc="转换进度"):
        example = ds[idx]
        converted = convert_to_dpo_format(example)

        if converted:
            converted["sample_id"] = f"helpsteer3_{len(all_samples)}"
            all_samples.append(converted)
        else:
            skipped += 1

    print(f"\n✅ 转换完成！")
    print(f"   有效样本: {len(all_samples)} 条")
    print(f"   跳过样本: {skipped} 条")

    if len(all_samples) == 0:
        print("❌ 没有有效样本！")
        return

    # 划分训练集和验证集
    print(f"\n📊 划分训练集和验证集（验证集比例: {args.validation_ratio}）...")

    val_size = int(len(all_samples) * args.validation_ratio)
    train_size = len(all_samples) - val_size

    train_samples = all_samples[:train_size]
    val_samples = all_samples[train_size:]

    print(f"   训练集: {train_size} 条")
    print(f"   验证集: {val_size} 条")

    # 保存训练集
    train_path = os.path.join(output_dir, "train.jsonl")
    with open(train_path, "w", encoding="utf-8") as f:
        for sample in train_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    # 保存验证集
    val_path = os.path.join(output_dir, "validation.jsonl")
    with open(val_path, "w", encoding="utf-8") as f:
        for sample in val_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    # 生成数据集信息
    from datetime import datetime

    info = {
        "dataset_name": "HelpSteer3-Preference",
        "source": "nvidia/HelpSteer3",
        "license": "CC-BY-4.0",
        "download_date": datetime.now().isoformat(),
        "download_method": "Hugging Face datasets library",
        "train_samples": train_size,
        "validation_samples": val_size,
        "total_samples": len(all_samples),
        "format": "DPO (prompt, chosen, rejected)",
        "files": {
            "train": "train.jsonl",
            "validation": "validation.jsonl"
        }
    }

    info_path = os.path.join(output_dir, "dataset_info.json")
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2, ensure_ascii=False)

    print(f"\n✅ 数据集信息已保存: {info_path}")

    print("\n" + "="*80)
    print("✅ 全部完成！")
    print("="*80)
    print(f"\n数据集位置: {output_dir}")
    print(f"训练集: {train_path} ({train_size} 样本)")
    print(f"验证集: {val_path} ({val_size} 样本)")
    print("\n下一步:")
    print(f"python scripts/train_dpo_test.py --train-data {train_path} --val-data {val_path}")


if __name__ == "__main__":
    main()
