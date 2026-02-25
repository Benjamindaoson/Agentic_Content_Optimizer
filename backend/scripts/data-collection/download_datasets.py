"""
数据集下载和预处理脚本
支持 TikTok-10M, 京东评论, Mercari MerRec 等数据集
"""

import os
import json
import pandas as pd
import polars as pl
from pathlib import Path
from typing import Dict, List, Optional
import logging
from datasets import load_dataset
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatasetDownloader:
    """数据集下载器"""

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def download_tiktok_10m(self) -> Path:
        """
        下载 TikTok-10M 数据集
        来源: https://huggingface.co/datasets/The-data-company/TikTok-10M
        """
        logger.info("Downloading TikTok-10M dataset...")

        output_path = self.data_dir / "tiktok-10m"
        output_path.mkdir(exist_ok=True)

        try:
            # 从 Hugging Face 下载
            dataset = load_dataset(
                "The-data-company/TikTok-10M",
                split="train",
                cache_dir=str(output_path)
            )

            # 保存为 Parquet
            df = dataset.to_pandas()
            parquet_path = output_path / "tiktok-10m.parquet"
            df.to_parquet(parquet_path, index=False)

            logger.info(f"TikTok-10M downloaded: {len(df)} records")
            logger.info(f"Saved to: {parquet_path}")

            return parquet_path

        except Exception as e:
            logger.error(f"Failed to download TikTok-10M: {e}")
            raise

    def download_jd_reviews(self) -> Path:
        """
        下载京东评论数据集
        来源: https://modelscope.cn/datasets/DAMO_NLP/jd
        """
        logger.info("Downloading JD Reviews dataset...")

        output_path = self.data_dir / "jd-reviews"
        output_path.mkdir(exist_ok=True)

        try:
            # 从 ModelScope 下载
            from modelscope.msdatasets import MsDataset

            dataset = MsDataset.load(
                "DAMO_NLP/jd",
                split="train",
                cache_dir=str(output_path)
            )

            # 转换为 DataFrame
            records = []
            for item in tqdm(dataset, desc="Processing JD Reviews"):
                records.append({
                    "review_text": item.get("text", ""),
                    "rating": item.get("label", 0),
                    "product_category": item.get("category", "")
                })

            df = pd.DataFrame(records)
            jsonl_path = output_path / "jd-reviews.jsonl"
            df.to_json(jsonl_path, orient="records", lines=True, force_ascii=False)

            logger.info(f"JD Reviews downloaded: {len(df)} records")
            logger.info(f"Saved to: {jsonl_path}")

            return jsonl_path

        except Exception as e:
            logger.error(f"Failed to download JD Reviews: {e}")
            raise

    def download_mercari_merrec(self) -> Path:
        """
        下载 Mercari MerRec 数据集
        来源: https://huggingface.co/datasets/mercari-us/merrec
        """
        logger.info("Downloading Mercari MerRec dataset...")

        output_path = self.data_dir / "mercari-merrec"
        output_path.mkdir(exist_ok=True)

        try:
            # 从 Hugging Face 下载
            dataset = load_dataset(
                "mercari-us/merrec",
                split="train",
                cache_dir=str(output_path)
            )

            # 保存为 Parquet
            df = dataset.to_pandas()
            parquet_path = output_path / "mercari-merrec.parquet"
            df.to_parquet(parquet_path, index=False)

            logger.info(f"Mercari MerRec downloaded: {len(df)} records")
            logger.info(f"Saved to: {parquet_path}")

            return parquet_path

        except Exception as e:
            logger.error(f"Failed to download Mercari MerRec: {e}")
            raise


class TikTokProcessor:
    """TikTok-10M 数据预处理器"""

    def __init__(self, input_path: Path, output_path: Path):
        self.input_path = input_path
        self.output_path = output_path

    def process(self) -> Path:
        """
        预处理 TikTok-10M 数据
        1. 同账号归一化
        2. 计算相对奖励
        3. 过滤异常值
        """
        logger.info("Processing TikTok-10M dataset...")

        # 使用 Polars 处理大规模数据
        df = pl.read_parquet(self.input_path)

        logger.info(f"Loaded {len(df)} records")

        # 1. 同账号归一化
        df = df.with_columns([
            # 计算每个作者的 baseline（最近10条的中位数）
            pl.col("digg_count")
              .over("author_id")
              .rolling_median(window_size=10)
              .alias("baseline_likes"),
        ])

        # 2. 计算相对增益
        df = df.with_columns([
            ((pl.col("digg_count") - pl.col("baseline_likes")) / pl.col("baseline_likes"))
              .fill_null(0)
              .alias("relative_gain"),
        ])

        # 3. 调整奖励（考虑曝光）
        df = df.with_columns([
            (pl.col("relative_gain") * (1 + pl.col("play_count")).log())
              .alias("adjusted_reward")
        ])

        # 4. 过滤异常值
        df = df.filter(
            (pl.col("adjusted_reward") > -3) &
            (pl.col("adjusted_reward") < 3) &
            (pl.col("baseline_likes").is_not_null())
        )

        # 5. 选择需要的字段
        df = df.select([
            "author_id",
            "publish_time",
            "play_count",
            "digg_count",
            "comment_count",
            "share_count",
            "description",
            "hashtags",
            "baseline_likes",
            "relative_gain",
            "adjusted_reward"
        ])

        # 6. 保存
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(self.output_path)

        logger.info(f"Processed {len(df)} records")
        logger.info(f"Saved to: {self.output_path}")

        # 7. 统计信息
        stats = {
            "total_records": len(df),
            "unique_authors": df["author_id"].n_unique(),
            "avg_reward": df["adjusted_reward"].mean(),
            "std_reward": df["adjusted_reward"].std(),
            "min_reward": df["adjusted_reward"].min(),
            "max_reward": df["adjusted_reward"].max(),
        }

        logger.info(f"Statistics: {json.dumps(stats, indent=2)}")

        return self.output_path


class JDReviewsProcessor:
    """京东评论数据预处理器"""

    def __init__(self, input_path: Path, output_path: Path):
        self.input_path = input_path
        self.output_path = output_path

    def process(self) -> Path:
        """
        预处理京东评论数据
        构建 SFT 训练格式
        """
        logger.info("Processing JD Reviews dataset...")

        # 加载数据
        df = pd.read_json(self.input_path, lines=True)

        logger.info(f"Loaded {len(df)} records")

        # 构建 SFT 格式
        sft_data = []
        for _, row in tqdm(df.iterrows(), total=len(df), desc="Building SFT data"):
            # 跳过空评论
            if not row["review_text"] or len(row["review_text"].strip()) < 10:
                continue

            # 构建指令
            category = row.get("product_category", "产品")
            instruction = f"请用口语化、自然的方式评价这个{category}"

            sft_data.append({
                "instruction": instruction,
                "input": "",
                "output": row["review_text"]
            })

        # 保存
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        sft_df = pd.DataFrame(sft_data)
        sft_df.to_json(self.output_path, orient="records", lines=True, force_ascii=False)

        logger.info(f"Processed {len(sft_df)} SFT records")
        logger.info(f"Saved to: {self.output_path}")

        return self.output_path


class MercariProcessor:
    """Mercari MerRec 数据预处理器"""

    def __init__(self, input_path: Path, output_path: Path):
        self.input_path = input_path
        self.output_path = output_path

        # 行为映射
        self.behavior_mapping = {
            "view": "impression",
            "click": "play",
            "favorite": "like",
            "purchase": "deep_engagement"
        }

    def process(self) -> Path:
        """
        预处理 Mercari 数据
        构建用户行为序列
        """
        logger.info("Processing Mercari MerRec dataset...")

        # 加载数据
        df = pl.read_parquet(self.input_path)

        logger.info(f"Loaded {len(df)} records")

        # 构建用户会话
        user_sessions = []

        # 按用户分组
        for user_id, group in tqdm(
            df.group_by("user_id"),
            desc="Building user sessions"
        ):
            # 按时间排序
            group = group.sort("timestamp")

            # 构建行为序列
            actions = []
            for row in group.iter_rows(named=True):
                action_type = row.get("action_type", "view")
                mapped_action = self.behavior_mapping.get(action_type, "impression")

                actions.append({
                    "action": mapped_action,
                    "item_id": row.get("item_id"),
                    "timestamp": row.get("timestamp"),
                    "features": {
                        "price": row.get("price"),
                        "category": row.get("category"),
                    }
                })

            user_sessions.append({
                "user_id": user_id,
                "actions": actions,
                "session_length": len(actions)
            })

        # 保存
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        sessions_df = pd.DataFrame(user_sessions)
        sessions_df.to_json(self.output_path, orient="records", lines=True)

        logger.info(f"Processed {len(sessions_df)} user sessions")
        logger.info(f"Saved to: {self.output_path}")

        return self.output_path


def main():
    """主函数"""
    # 1. 下载数据集
    downloader = DatasetDownloader(data_dir="./data/raw")

    # 下载 TikTok-10M
    tiktok_path = downloader.download_tiktok_10m()

    # 下载京东评论
    jd_path = downloader.download_jd_reviews()

    # 下载 Mercari
    mercari_path = downloader.download_mercari_merrec()

    # 2. 预处理数据
    processed_dir = Path("./data/processed")

    # 处理 TikTok-10M
    tiktok_processor = TikTokProcessor(
        input_path=tiktok_path,
        output_path=processed_dir / "tiktok-10m-processed.parquet"
    )
    tiktok_processor.process()

    # 处理京东评论
    jd_processor = JDReviewsProcessor(
        input_path=jd_path,
        output_path=processed_dir / "jd-reviews-sft.jsonl"
    )
    jd_processor.process()

    # 处理 Mercari
    mercari_processor = MercariProcessor(
        input_path=mercari_path,
        output_path=processed_dir / "mercari-sessions.jsonl"
    )
    mercari_processor.process()

    logger.info("All datasets processed successfully!")


if __name__ == "__main__":
    main()
