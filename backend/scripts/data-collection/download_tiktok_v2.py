"""
TikTok-10M 完全 D 盘下载脚本
通过修改系统环境变量,强制所有缓存都在 D 盘
"""

import os
import sys
from pathlib import Path

# ============================================
# 关键：在导入任何 HuggingFace 库之前设置环境变量
# ============================================

# 设置项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "tiktok-10m"
CACHE_DIR = DATA_DIR / ".cache"

# 创建目录
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# 强制设置所有 HuggingFace 相关的环境变量到 D 盘
os.environ["HF_HOME"] = str(CACHE_DIR / "hf_home")
os.environ["HF_DATASETS_CACHE"] = str(CACHE_DIR / "datasets")
os.environ["TRANSFORMERS_CACHE"] = str(CACHE_DIR / "transformers")
os.environ["HF_HUB_CACHE"] = str(CACHE_DIR / "hub")
os.environ["HUGGINGFACE_HUB_CACHE"] = str(CACHE_DIR / "hub")
os.environ["HF_ASSETS_CACHE"] = str(CACHE_DIR / "assets")

# 禁用符号链接警告
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# 打印环境变量确认
print("=" * 60)
print("Environment Variables Set:")
print("=" * 60)
for key in ["HF_HOME", "HF_DATASETS_CACHE", "TRANSFORMERS_CACHE", "HF_HUB_CACHE"]:
    print(f"{key}: {os.environ.get(key)}")
print("=" * 60)

# 现在才导入 HuggingFace 库
import pandas as pd
from datasets import load_dataset, DownloadConfig
from tqdm import tqdm
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TikTokDownloaderV2:
    """TikTok-10M 下载器 V2 - 完全 D 盘方案"""

    def __init__(
        self,
        output_dir: Path = DATA_DIR,
        batch_size: int = 50000,  # 减小批次大小
        max_batches: int = 10
    ):
        self.output_dir = output_dir
        self.batch_size = batch_size
        self.max_batches = max_batches

        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"Cache directory: {CACHE_DIR}")

    def download_batch(self, batch_idx: int, start: int, end: int) -> Path:
        """下载单个批次"""
        logger.info(f"Downloading batch {batch_idx}: records {start} to {end}")

        try:
            # 创建下载配置
            download_config = DownloadConfig(
                cache_dir=str(CACHE_DIR / "datasets"),
                force_download=False,
                resume_download=True,
                num_proc=4  # 使用多进程加速
            )

            # 下载数据
            dataset = load_dataset(
                "The-data-company/TikTok-10M",
                split=f"train[{start}:{end}]",
                cache_dir=str(CACHE_DIR / "datasets"),
                download_config=download_config
            )

            # 转换为 DataFrame
            df = dataset.to_pandas()

            # 保存为 Parquet
            batch_file = self.output_dir / f"batch_{batch_idx:03d}.parquet"
            df.to_parquet(batch_file, index=False, compression='snappy')

            file_size_mb = batch_file.stat().st_size / 1024 / 1024
            logger.info(f"✅ Batch {batch_idx} saved: {len(df):,} records, {file_size_mb:.2f} MB")

            return batch_file

        except Exception as e:
            logger.error(f"❌ Batch {batch_idx} failed: {e}")
            raise

    def download_all(self) -> list[Path]:
        """下载所有批次"""
        logger.info("=" * 60)
        logger.info("Starting TikTok-10M Download (All to D Drive)")
        logger.info("=" * 60)
        logger.info(f"Batch size: {self.batch_size:,}")
        logger.info(f"Max batches: {self.max_batches}")
        logger.info("=" * 60)

        batch_files = []
        batch_idx = 0
        start = 0

        while batch_idx < self.max_batches:
            end = start + self.batch_size

            try:
                batch_file = self.download_batch(batch_idx, start, end)
                batch_files.append(batch_file)

                batch_idx += 1
                start = end

                # 保存进度
                self._save_progress(batch_idx, start, batch_files)

            except Exception as e:
                logger.error(f"Batch {batch_idx} error: {e}")
                if "out of bounds" in str(e).lower():
                    logger.info("Reached end of dataset")
                    break
                batch_idx += 1
                start = end

        logger.info("=" * 60)
        logger.info(f"✅ Download completed: {len(batch_files)} batches")
        logger.info("=" * 60)

        return batch_files

    def _save_progress(self, batch_idx: int, start: int, batch_files: list[Path]):
        """保存进度"""
        progress_file = self.output_dir / "download_progress.json"
        progress = {
            "last_batch": batch_idx,
            "last_start": start,
            "total_batches": len(batch_files),
            "batch_files": [str(f) for f in batch_files]
        }
        with open(progress_file, "w") as f:
            json.dump(progress, f, indent=2)

    def get_statistics(self) -> dict:
        """获取统计信息"""
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
            "batch_files": [str(f) for f in batch_files]
        }


def check_disk_space():
    """检查 D 盘空间"""
    import shutil

    total, used, free = shutil.disk_usage("D:\\")

    print("\n" + "=" * 60)
    print("D Drive Disk Space:")
    print("=" * 60)
    print(f"Total: {total / (1024**3):.2f} GB")
    print(f"Used:  {used / (1024**3):.2f} GB")
    print(f"Free:  {free / (1024**3):.2f} GB")
    print("=" * 60)

    # 检查是否有足够空间（至少需要 5GB）
    if free < 5 * 1024**3:
        logger.warning(f"⚠️  Low disk space on D drive: {free / (1024**3):.2f} GB")
        return False

    return True


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="TikTok-10M Downloader V2")
    parser.add_argument("--batch-size", type=int, default=50000, help="Batch size")
    parser.add_argument("--max-batches", type=int, default=10, help="Max batches")
    parser.add_argument("--stats", action="store_true", help="Show stats only")

    args = parser.parse_args()

    # 检查磁盘空间
    if not check_disk_space():
        logger.error("Insufficient disk space on D drive")
        sys.exit(1)

    # 创建下载器
    downloader = TikTokDownloaderV2(
        output_dir=DATA_DIR,
        batch_size=args.batch_size,
        max_batches=args.max_batches
    )

    # 显示统计信息
    if args.stats:
        stats = downloader.get_statistics()
        print(json.dumps(stats, indent=2))
        return

    # 下载数据
    batch_files = downloader.download_all()

    # 显示统计信息
    stats = downloader.get_statistics()
    print("\n" + "=" * 60)
    print("Download Statistics:")
    print("=" * 60)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
