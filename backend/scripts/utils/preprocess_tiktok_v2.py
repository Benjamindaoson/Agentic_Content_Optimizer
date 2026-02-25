"""
TikTok-10M 数据预处理 - 改进版
提取结构化特征用于 SFT 训练
"""

import polars as pl
import re
from pathlib import Path
from typing import Dict, List
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TikTokFeatureExtractor:
    """TikTok 特征提取器 - 提取爆款结构特征"""

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.df = None

    def load_data(self):
        """加载所有 Parquet 文件"""
        logger.info(f"Loading data from {self.data_dir}")

        # 只加载 batch 文件，跳过 train 文件（可能被占用）
        parquet_files = list(self.data_dir.glob("batch_*.parquet"))
        logger.info(f"Found {len(parquet_files)} batch parquet files")

        if len(parquet_files) == 0:
            # 如果没有 batch 文件，尝试加载 train 文件
            parquet_files = list(self.data_dir.glob("train-*.parquet"))
            logger.info(f"Found {len(parquet_files)} train parquet files")

        # 读取所有文件
        dfs = []
        for file in sorted(parquet_files):
            try:
                logger.info(f"Reading {file.name}")
                df = pl.read_parquet(file)
                dfs.append(df)
            except Exception as e:
                logger.warning(f"Failed to read {file.name}: {e}")
                continue

        if not dfs:
            raise ValueError("No parquet files could be loaded")

        self.df = pl.concat(dfs)
        logger.info(f"Loaded {len(self.df)} records from {len(dfs)} files")

    def extract_hook_features(self, text: str) -> Dict:
        """提取前三秒钩子特征"""
        # 前20个字作为钩子
        hook = text[:20] if len(text) >= 20 else text

        features = {
            "hook_text": hook,
            "has_question": "?" in hook or "？" in hook,
            "has_number": any(char.isdigit() for char in hook),
            "has_exclamation": "!" in hook or "！" in hook,
            "hook_length": len(hook)
        }

        # 检测强情绪词
        emotion_words = ["震惊", "必看", "绝了", "太", "超", "爆", "火", "热"]
        features["emotion_word_count"] = sum(1 for word in emotion_words if word in hook)

        return features

    def extract_structure_features(self, text: str) -> Dict:
        """提取文案结构特征"""
        features = {
            "total_length": len(text),
            "sentence_count": text.count("。") + text.count("！") + text.count("？"),
            "paragraph_count": len(text.split("\n")),
            "question_count": text.count("?") + text.count("？"),
            "exclamation_count": text.count("!") + text.count("！")
        }

        # CTA 检测
        cta_words = ["点赞", "关注", "评论", "转发", "收藏", "双击", "分享"]
        features["has_cta"] = any(word in text for word in cta_words)

        # 数字密度
        digit_count = sum(1 for char in text if char.isdigit())
        features["digit_density"] = digit_count / len(text) if len(text) > 0 else 0

        return features

    def extract_emotion_features(self, text: str) -> Dict:
        """提取情绪特征"""
        # 情绪词典
        positive_words = ["爱", "喜欢", "开心", "快乐", "幸福", "美好", "棒", "赞"]
        negative_words = ["讨厌", "难过", "痛苦", "失望", "糟糕", "差"]
        surprise_words = ["震惊", "惊讶", "意外", "没想到", "竟然"]

        features = {
            "positive_count": sum(1 for word in positive_words if word in text),
            "negative_count": sum(1 for word in negative_words if word in text),
            "surprise_count": sum(1 for word in surprise_words if word in text)
        }

        # 强调词
        emphasis_words = ["太", "超", "非常", "特别", "真的", "简直", "极其"]
        features["emphasis_count"] = sum(1 for word in emphasis_words if word in text)

        # 情绪强度
        total_emotion = features["positive_count"] + features["negative_count"] + features["surprise_count"]
        features["emotion_intensity"] = total_emotion / len(text) * 100 if len(text) > 0 else 0

        return features

    def process_dataset(self, output_path: str, sample_size: int = None):
        """处理数据集并提取特征"""
        logger.info("Processing dataset...")

        if self.df is None:
            self.load_data()

        # 采样（如果指定）
        if sample_size and sample_size < len(self.df):
            logger.info(f"Sampling {sample_size} records")
            df = self.df.sample(n=sample_size, seed=42)
        else:
            df = self.df

        # 提取特征
        processed_records = []

        for i, row in enumerate(df.iter_rows(named=True)):
            if i % 10000 == 0:
                logger.info(f"Processed {i}/{len(df)} records")

            # 获取文本
            text = row.get("desc", row.get("description", ""))
            if not text or len(text) < 10:
                continue

            # 提取各类特征
            hook_features = self.extract_hook_features(text)
            structure_features = self.extract_structure_features(text)
            emotion_features = self.extract_emotion_features(text)

            # 计算互动分数
            engagement_score = (
                row.get("digg_count", 0) +
                row.get("comment_count", 0) * 2 +
                row.get("share_count", 0) * 3
            )

            # 判断是否爆款（top 20%）
            is_viral = engagement_score > df["digg_count"].quantile(0.8)

            # 组合记录
            record = {
                # 原始数据
                "text": text,
                "author_id": row.get("author_id", ""),
                "hashtags": str(row.get("hashtags", [])),

                # 互动数据
                "digg_count": row.get("digg_count", 0),
                "comment_count": row.get("comment_count", 0),
                "share_count": row.get("share_count", 0),
                "play_count": row.get("play_count", 0),
                "engagement_score": engagement_score,
                "is_viral": is_viral,

                # 特征
                **hook_features,
                **structure_features,
                **emotion_features
            }

            processed_records.append(record)

        # 转换为 DataFrame
        processed_df = pl.DataFrame(processed_records)

        # 保存
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        processed_df.write_parquet(output_path)
        logger.info(f"Saved {len(processed_df)} processed records to {output_path}")

        # 打印统计
        self._print_statistics(processed_df)

        return processed_df

    def _print_statistics(self, df: pl.DataFrame):
        """打印统计信息"""
        logger.info("\n" + "=" * 60)
        logger.info("Dataset Statistics")
        logger.info("=" * 60)

        logger.info(f"\nBasic Stats:")
        logger.info(f"  Total records: {len(df)}")
        logger.info(f"  Viral posts:   {df['is_viral'].sum()} ({df['is_viral'].mean()*100:.1f}%)")

        logger.info(f"\nHook Features:")
        logger.info(f"  Avg hook length:     {df['hook_length'].mean():.1f}")
        logger.info(f"  Has question:        {df['has_question'].mean()*100:.1f}%")
        logger.info(f"  Has number:          {df['has_number'].mean()*100:.1f}%")

        logger.info("=" * 60)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="TikTok Data Preprocessing")
    parser.add_argument("--data-dir", type=str, required=True, help="Directory with parquet files")
    parser.add_argument("--output", type=str, required=True, help="Output path for processed data")
    parser.add_argument("--sample-size", type=int, help="Sample size (optional)")

    args = parser.parse_args()

    # 创建提取器
    extractor = TikTokFeatureExtractor(data_dir=args.data_dir)

    # 处理数据
    extractor.process_dataset(
        output_path=args.output,
        sample_size=args.sample_size
    )


if __name__ == "__main__":
    main()
