"""
TikTok-10M 数据预处理脚本
处理下载的原始数据，计算奖励值
"""

import json
import logging
from pathlib import Path
from typing import Dict, List
from collections import defaultdict
import statistics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TikTokPreprocessor:
    """TikTok 数据预处理器"""

    def __init__(self, input_file: str, output_file: str):
        self.input_file = Path(input_file)
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

    def preprocess(self):
        """预处理数据"""
        logger.info(f"Loading data from {self.input_file}...")

        # 读取数据
        data = []
        with open(self.input_file, "r", encoding="utf-8") as f:
            for line in f:
                data.append(json.loads(line))

        logger.info(f"Loaded {len(data)} records")

        # 按作者分组
        logger.info("Grouping by author...")
        author_posts = defaultdict(list)
        for record in data:
            author_id = record.get("author_id") or record.get("authorId") or "unknown"
            author_posts[author_id].append(record)

        # 计算 baseline 和奖励
        logger.info("Calculating rewards...")
        processed_data = []

        for author_id, posts in author_posts.items():
            # 按时间排序
            posts.sort(key=lambda x: x.get("create_time", 0) or x.get("createTime", 0))

            for i, post in enumerate(posts):
                # 获取点赞数和播放数
                likes = post.get("digg_count") or post.get("diggCount") or 0
                plays = post.get("play_count") or post.get("playCount") or 0

                # 计算 baseline (最近 10 条的中位数)
                start_idx = max(0, i - 10)
                recent_posts = posts[start_idx:i] if i > 0 else [post]
                recent_likes = [
                    p.get("digg_count") or p.get("diggCount") or 0
                    for p in recent_posts
                ]

                if recent_likes:
                    baseline = statistics.median(recent_likes)
                else:
                    baseline = 1  # 避免除零

                # 计算相对增益
                if baseline > 0:
                    relative_gain = (likes - baseline) / baseline
                else:
                    relative_gain = 0

                # 计算调整后的奖励
                import math
                adjusted_reward = relative_gain * math.log(1 + plays)

                # 添加计算字段
                processed_record = {
                    **post,
                    "baseline_likes": baseline,
                    "relative_gain": relative_gain,
                    "adjusted_reward": adjusted_reward
                }

                processed_data.append(processed_record)

        # 保存处理后的数据
        logger.info(f"Saving processed data to {self.output_file}...")
        with open(self.output_file, "w", encoding="utf-8") as f:
            for record in processed_data:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        logger.info(f"Preprocessing completed! Saved {len(processed_data)} records")

        # 统计信息
        self._print_statistics(processed_data)

    def _print_statistics(self, data: List[Dict]):
        """打印统计信息"""
        logger.info("\n" + "=" * 60)
        logger.info("Dataset Statistics")
        logger.info("=" * 60)

        total_records = len(data)
        logger.info(f"Total records: {total_records}")

        # 点赞数统计
        likes = [r.get("digg_count") or r.get("diggCount") or 0 for r in data]
        logger.info(f"\nLikes:")
        logger.info(f"  Mean: {statistics.mean(likes):.2f}")
        logger.info(f"  Median: {statistics.median(likes):.2f}")
        logger.info(f"  Max: {max(likes)}")

        # 播放数统计
        plays = [r.get("play_count") or r.get("playCount") or 0 for r in data]
        logger.info(f"\nPlays:")
        logger.info(f"  Mean: {statistics.mean(plays):.2f}")
        logger.info(f"  Median: {statistics.median(plays):.2f}")
        logger.info(f"  Max: {max(plays)}")

        # 奖励统计
        rewards = [r.get("adjusted_reward", 0) for r in data]
        logger.info(f"\nAdjusted Rewards:")
        logger.info(f"  Mean: {statistics.mean(rewards):.4f}")
        logger.info(f"  Median: {statistics.median(rewards):.4f}")
        logger.info(f"  Min: {min(rewards):.4f}")
        logger.info(f"  Max: {max(rewards):.4f}")


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("TikTok-10M Data Preprocessing")
    logger.info("=" * 60)

    preprocessor = TikTokPreprocessor(
        input_file="D:/SalesBoost/data/raw/tiktok-10m-sample.jsonl",
        output_file="D:/SalesBoost/data/processed/tiktok-10m-processed.jsonl"
    )

    preprocessor.preprocess()

    logger.info("\nPreprocessing completed!")
    logger.info("Next step: Train models")


if __name__ == "__main__":
    main()
