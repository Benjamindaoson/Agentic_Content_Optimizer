"""
TikTok-10M 直接下载脚本
完全绕过 Hugging Face 缓存,直接下载到 D 盘
使用 HTTP 流式下载,避免 C 盘空间问题
"""

import os
import requests
import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path
from typing import Optional
import logging
from tqdm import tqdm
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DirectTikTokDownloader:
    """TikTok-10M 直接下载器"""

    def __init__(self, output_dir: str = "D:\\growth-flywheel-2.5\\backend\\data\\raw\\tiktok-10m"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Hugging Face 数据集 URL
        self.base_url = "https://huggingface.co/datasets/The-data-company/TikTok-10M/resolve/main"

        logger.info(f"Output directory: {self.output_dir}")

    def download_file(self, filename: str, output_path: Path) -> bool:
        """
        直接下载文件

        Args:
            filename: 文件名
            output_path: 输出路径

        Returns:
            是否成功
        """
        url = f"{self.base_url}/{filename}"
        logger.info(f"Downloading: {url}")

        try:
            # 流式下载
            response = requests.get(url, stream=True)
            response.raise_for_status()

            # 获取文件大小
            total_size = int(response.headers.get('content-length', 0))

            # 下载并保存
            with open(output_path, 'wb') as f:
                with tqdm(total=total_size, unit='B', unit_scale=True, desc=filename) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))

            logger.info(f"Downloaded: {output_path} ({output_path.stat().st_size / 1024 / 1024:.2f} MB)")
            return True

        except Exception as e:
            logger.error(f"Failed to download {filename}: {e}")
            return False

    def list_dataset_files(self) -> list[str]:
        """
        列出数据集中的所有文件

        Returns:
            文件名列表
        """
        # TikTok-10M 数据集有 10 个 Parquet 文件
        files = []
        for i in range(10):
            filename = f"data/train-{i:05d}-of-00010.parquet"
            files.append(filename)

        return files

    def download_sample(self, num_files: int = 5) -> list[Path]:
        """
        下载样本数据

        Args:
            num_files: 下载文件数量

        Returns:
            下载的文件路径列表
        """
        logger.info(f"Downloading {num_files} files...")

        downloaded_files = []

        for i in range(min(num_files, 10)):  # 最多 10 个文件
            filename = f"data/train-{i:05d}-of-00010.parquet"
            output_filename = f"train-{i:05d}-of-00010.parquet"
            output_path = self.output_dir / output_filename

            if self.download_file(filename, output_path):
                downloaded_files.append(output_path)
            else:
                logger.warning(f"Failed to download file {i}, skipping...")

        logger.info(f"Downloaded {len(downloaded_files)} files")
        return downloaded_files

    def get_statistics(self) -> dict:
        """获取下载统计信息"""
        parquet_files = list(self.output_dir.glob("*.parquet"))

        if not parquet_files:
            return {"status": "no_data"}

        total_records = 0
        total_size = 0

        for file in parquet_files:
            try:
                table = pq.read_table(file)
                total_records += len(table)
                total_size += file.stat().st_size
            except Exception as e:
                logger.warning(f"Failed to read {file}: {e}")

        return {
            "status": "success",
            "total_files": len(parquet_files),
            "total_records": total_records,
            "total_size_mb": total_size / 1024 / 1024,
            "files": [str(f) for f in parquet_files]
        }


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="Direct TikTok-10M Downloader")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="D:\\growth-flywheel-2.5\\backend\\data\\raw\\tiktok-10m",
        help="Output directory"
    )
    parser.add_argument(
        "--num-files",
        type=int,
        default=5,
        help="Number of files to download"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show statistics only"
    )

    args = parser.parse_args()

    # 创建下载器
    downloader = DirectTikTokDownloader(output_dir=args.output_dir)

    # 显示统计信息
    if args.stats:
        stats = downloader.get_statistics()
        print(json.dumps(stats, indent=2))
        return

    # 下载样本
    downloaded_files = downloader.download_sample(num_files=args.num_files)

    # 显示统计信息
    stats = downloader.get_statistics()
    print("\n" + "=" * 60)
    print("Download Statistics:")
    print("=" * 60)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
