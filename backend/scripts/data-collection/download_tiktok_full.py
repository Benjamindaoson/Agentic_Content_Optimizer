"""
使用 Hugging Face Datasets Server API 下载完整的 TikTok-10M 数据集
无需安装 datasets 库，直接通过 HTTP API 获取数据
"""

import json
import requests
from pathlib import Path
from typing import List, Dict
import logging
from tqdm import tqdm
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HFDatasetDownloader:
    """Hugging Face Datasets Server API 下载器"""

    def __init__(self, output_dir: str = "D:/SalesBoost/data/raw"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.base_url = "https://datasets-server.huggingface.co/rows"

    def download_tiktok_10m(
        self,
        batch_size: int = 100,
        max_samples: int = 10000000,  # 1000万条
        save_every: int = 10000,      # 每1万条保存一次
        retry_delay: int = 10         # 遇到429错误时等待时间
    ) -> Path:
        """
        下载 TikTok-10M 数据集

        Args:
            batch_size: 每次请求的样本数 (最大 100)
            max_samples: 最大下载样本数 (10000000 = 1000万条)
            save_every: 每下载多少条保存一次
            retry_delay: 遇到429错误时等待时间（秒）
        """
        logger.info(f"Starting TikTok-10M FULL download via API...")
        logger.info(f"Target samples: {max_samples:,}")
        logger.info(f"Estimated time: 50-80 hours")
        logger.info(f"Save frequency: every {save_every:,} records")

        output_file = self.output_dir / "tiktok-10m-full.jsonl"

        # 检查是否已有数据（断点续传）
        existing_count = 0
        if output_file.exists():
            with open(output_file, "r", encoding="utf-8") as f:
                existing_count = sum(1 for _ in f)
            logger.info(f"Found existing data: {existing_count:,} records")
            logger.info("Resuming from last position...")

        offset = existing_count
        consecutive_429_errors = 0
        max_consecutive_429 = 5

        with tqdm(total=max_samples, initial=offset, desc="Downloading") as pbar:
            while offset < max_samples:
                try:
                    # 构建请求 URL
                    params = {
                        "dataset": "The-data-company/TikTok-10M",
                        "config": "default",
                        "split": "train",
                        "offset": offset,
                        "length": min(batch_size, max_samples - offset)
                    }

                    # 发送请求
                    response = requests.get(self.base_url, params=params, timeout=30)

                    # 处理 429 错误（请求过快）
                    if response.status_code == 429:
                        consecutive_429_errors += 1
                        wait_time = retry_delay * consecutive_429_errors
                        logger.warning(f"Rate limit hit (429). Waiting {wait_time}s... ({consecutive_429_errors}/{max_consecutive_429})")
                        time.sleep(wait_time)

                        if consecutive_429_errors >= max_consecutive_429:
                            logger.warning(f"Too many 429 errors. Increasing delay to {retry_delay * 2}s")
                            retry_delay *= 2
                            consecutive_429_errors = 0
                        continue

                    response.raise_for_status()
                    consecutive_429_errors = 0  # 重置计数器

                    # 解析响应
                    data = response.json()

                    if "rows" not in data:
                        logger.error(f"Unexpected response format: {data}")
                        break

                    rows = data["rows"]
                    if not rows:
                        logger.info("No more data available")
                        break

                    # 追加保存数据（不加载到内存）
                    with open(output_file, "a", encoding="utf-8") as f:
                        for row in rows:
                            record = row.get("row", {})
                            f.write(json.dumps(record, ensure_ascii=False) + "\n")

                    # 更新进度
                    offset += len(rows)
                    pbar.update(len(rows))

                    # 定期报告进度
                    if offset % save_every == 0:
                        logger.info(f"Progress: {offset:,} / {max_samples:,} ({offset/max_samples*100:.2f}%)")
                        logger.info(f"Saved to: {output_file}")

                    # 避免请求过快（动态调整）
                    time.sleep(0.2 if consecutive_429_errors == 0 else 0.5)

                except requests.exceptions.RequestException as e:
                    logger.error(f"Request failed at offset {offset:,}: {e}")
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    continue

                except KeyboardInterrupt:
                    logger.info("\nDownload interrupted by user")
                    logger.info(f"Downloaded {offset:,} records so far")
                    logger.info(f"Data saved to: {output_file}")
                    logger.info("Run the script again to resume from this position")
                    return output_file

                except Exception as e:
                    logger.error(f"Error at offset {offset:,}: {e}")
                    logger.info("Saving progress and continuing...")
                    time.sleep(5)
                    continue

        logger.info(f"Download completed! Total records: {offset:,}")
        logger.info(f"Saved to: {output_file}")

        return output_file

    def preview_data(self, limit: int = 5):
        """预览前几条数据"""
        logger.info("Fetching preview data...")

        params = {
            "dataset": "The-data-company/TikTok-10M",
            "config": "default",
            "split": "train",
            "offset": 0,
            "length": limit
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if "rows" in data:
                logger.info(f"Preview of first {limit} records:")
                for i, row in enumerate(data["rows"][:limit]):
                    record = row.get("row", {})
                    logger.info(f"\n--- Record {i+1} ---")
                    logger.info(f"ID: {record.get('id', 'N/A')}")
                    logger.info(f"Description: {record.get('desc', 'N/A')[:100]}...")
                    logger.info(f"Likes: {record.get('digg_count', 'N/A')}")
                    logger.info(f"Views: {record.get('play_count', 'N/A')}")
                    logger.info(f"Comments: {record.get('comment_count', 'N/A')}")

        except Exception as e:
            logger.error(f"Failed to fetch preview: {e}")


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("TikTok-10M FULL Dataset Downloader (API Version)")
    logger.info("=" * 60)

    downloader = HFDatasetDownloader(output_dir="D:/SalesBoost/data/raw")

    # 预览数据
    logger.info("\n[Step 1] Previewing data...")
    downloader.preview_data(limit=3)

    # 下载完整数据集
    logger.info("\n[Step 2] Downloading FULL dataset (10 MILLION records)...")
    logger.info("=" * 60)
    logger.info("IMPORTANT NOTES:")
    logger.info("- This will download 10 MILLION records (~50GB)")
    logger.info("- Estimated time: 50-80 hours")
    logger.info("- Data saved to: D:/SalesBoost/data/raw/tiktok-10m-full.jsonl")
    logger.info("- Supports resume: if interrupted, run again to continue")
    logger.info("- Press Ctrl+C to stop (progress will be saved)")
    logger.info("=" * 60)

    input("\nPress Enter to start downloading, or Ctrl+C to cancel...")

    output_file = downloader.download_tiktok_10m(
        batch_size=100,
        max_samples=10000000,  # 1000万条
        save_every=10000,      # 每1万条报告一次
        retry_delay=10         # 遇到429错误等待10秒
    )

    logger.info("\n" + "=" * 60)
    logger.info("Download completed!")
    logger.info("=" * 60)
    logger.info(f"Output file: {output_file}")
    logger.info("\nNext steps:")
    logger.info("1. Check the downloaded data")
    logger.info("2. Run preprocessing: python backend/scripts/preprocess_tiktok.py")
    logger.info("3. Train models")


if __name__ == "__main__":
    main()
