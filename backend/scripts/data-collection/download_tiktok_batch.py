"""
TikTok-10M 分批下载脚本
直接下载到 D:\growth-flywheel-2.5\backend\data\raw\
避免占用 C 盘空间
"""

import os
import json
import pandas as pd
from pathlib import Path
from typing import Optional
import logging
from datasets import load_dataset
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TikTokBatchDownloader:
    """TikTok-10M 分批下载器"""

    def __init__(
        self,
        output_dir: str = "./data/raw/tiktok-10m",
        batch_size: int = 100000,
        max_batches: Optional[int] = None
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.batch_size = batch_size
        self.max_batches = max_batches

        # 设置环境变量,强制使用项目目录作为缓存
        cache_dir = str(self.output_dir / ".cache")
        os.environ["HF_HOME"] = cache_dir
        os.environ["HF_DATASETS_CACHE"] = cache_dir
        os.environ["TRANSFORMERS_CACHE"] = cache_dir
        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

        logger.info(f"Cache directory: {cache_dir}")
        logger.info(f"Output directory: {self.output_dir}")

    def download_batch(self, batch_idx: int, start: int, end: int) -> Path:
        """
        下载单个批次

        Args:
            batch_idx: 批次索引
            start: 起始索引
            end: 结束索引

        Returns:
            保存的文件路径
        """
        logger.info(f"Downloading batch {batch_idx}: records {start} to {end}")

        try:
            from datasets import DownloadConfig

            # 强制使用 D 盘缓存
            download_config = DownloadConfig(
                cache_dir=str(self.output_dir / ".cache"),
                force_download=False,
                resume_download=True
            )

            # 下载指定范围的数据
            dataset = load_dataset(
                "The-data-company/TikTok-10M",
                split=f"train[{start}:{end}]",
                cache_dir=str(self.output_dir / ".cache"),
                download_config=download_config
            )

            # 转换为 DataFrame
            df = dataset.to_pandas()

            # 保存为 Parquet
            batch_file = self.output_dir / f"batch_{batch_idx:03d}.parquet"
            df.to_parquet(batch_file, index=False)

            logger.info(f"Batch {batch_idx} saved: {len(df)} records -> {batch_file}")
            logger.info(f"File size: {batch_file.stat().st_size / 1024 / 1024:.2f} MB")

            return batch_file

        except Exception as e:
            logger.error(f"Failed to download batch {batch_idx}: {e}")
            raise

    def download_all_batches(self) -> list[Path]:
        """
        下载所有批次

        Returns:
            所有批次文件路径列表
        """
        logger.info("=" * 60)
        logger.info("Starting TikTok-10M Batch Download")
        logger.info("=" * 60)
        logger.info(f"Batch size: {self.batch_size:,}")
        logger.info(f"Max batches: {self.max_batches or 'All'}")
        logger.info(f"Output: {self.output_dir}")
        logger.info("=" * 60)

        batch_files = []
        batch_idx = 0
        start = 0

        while True:
            # 检查是否达到最大批次数
            if self.max_batches and batch_idx >= self.max_batches:
                logger.info(f"Reached max batches: {self.max_batches}")
                break

            end = start + self.batch_size

            try:
                # 下载批次
                batch_file = self.download_batch(batch_idx, start, end)
                batch_files.append(batch_file)

                # 更新进度
                batch_idx += 1
                start = end

                # 保存进度
                self._save_progress(batch_idx, start, batch_files)

            except Exception as e:
                logger.error(f"Batch {batch_idx} failed: {e}")
                # 如果是因为超出数据集范围,则停止
                if "out of bounds" in str(e).lower() or "index" in str(e).lower():
                    logger.info("Reached end of dataset")
                    break
                # 其他错误则继续下一批次
                batch_idx += 1
                start = end
                continue

        logger.info("=" * 60)
        logger.info(f"Download completed: {len(batch_files)} batches")
        logger.info("=" * 60)

        return batch_files

    def _save_progress(self, batch_idx: int, start: int, batch_files: list[Path]):
        """保存下载进度"""
        progress_file = self.output_dir / "download_progress.json"

        progress = {
            "last_batch": batch_idx,
            "last_start": start,
            "total_batches": len(batch_files),
            "batch_files": [str(f) for f in batch_files]
        }

        with open(progress_file, "w") as f:
            json.dump(progress, f, indent=2)

    def merge_batches(self, output_file: Optional[Path] = None) -> Path:
        """
        合并所有批次文件

        Args:
            output_file: 输出文件路径

        Returns:
            合并后的文件路径
        """
        logger.info("Merging all batches...")

        # 查找所有批次文件
        batch_files = sorted(self.output_dir.glob("batch_*.parquet"))

        if not batch_files:
            raise ValueError("No batch files found")

        logger.info(f"Found {len(batch_files)} batch files")

        # 读取并合并
        dfs = []
        for batch_file in tqdm(batch_files, desc="Loading batches"):
            df = pd.read_parquet(batch_file)
            dfs.append(df)

        merged_df = pd.concat(dfs, ignore_index=True)

        # 保存合并后的文件
        if output_file is None:
            output_file = self.output_dir / "tiktok-10m-merged.parquet"

        merged_df.to_parquet(output_file, index=False)

        logger.info(f"Merged {len(merged_df):,} records -> {output_file}")
        logger.info(f"File size: {output_file.stat().st_size / 1024 / 1024:.2f} MB")

        return output_file

    def get_statistics(self) -> dict:
        """获取下载统计信息"""
        batch_files = sorted(self.output_dir.glob("batch_*.parquet"))

        if not batch_files:
            return {"status": "no_data"}

        total_records = 0
        total_size = 0

        for batch_file in batch_files:
            df = pd.read_parquet(batch_file)
            total_records += len(df)
            total_size += batch_file.stat().st_size

        return {
            "status": "success",
            "total_batches": len(batch_files),
            "total_records": total_records,
            "total_size_mb": total_size / 1024 / 1024,
            "avg_records_per_batch": total_records / len(batch_files),
            "batch_files": [str(f) for f in batch_files]
        }


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="TikTok-10M Batch Downloader")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./data/raw/tiktok-10m",
        help="Output directory"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100000,
        help="Batch size (default: 100,000)"
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=None,
        help="Maximum number of batches to download (default: all)"
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Merge all batches after download"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show statistics only"
    )

    args = parser.parse_args()

    # 创建下载器
    downloader = TikTokBatchDownloader(
        output_dir=args.output_dir,
        batch_size=args.batch_size,
        max_batches=args.max_batches
    )

    # 显示统计信息
    if args.stats:
        stats = downloader.get_statistics()
        print(json.dumps(stats, indent=2))
        return

    # 下载批次
    batch_files = downloader.download_all_batches()

    # 合并批次
    if args.merge:
        downloader.merge_batches()

    # 显示统计信息
    stats = downloader.get_statistics()
    print("\n" + "=" * 60)
    print("Download Statistics:")
    print("=" * 60)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
