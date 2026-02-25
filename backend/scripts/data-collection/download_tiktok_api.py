"""
使用 Hugging Face Datasets Server API 下载 TikTok-10M 数据集
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
        max_samples: int = 10000,
        save_every: int = 1000
    ) -> Path:
        """
        下载 TikTok-10M 数据集

        Args:
            batch_size: 每次请求的样本数 (最大 100)
            max_samples: 最大下载样本数 (10000 = 1万条，用于测试)
            save_every: 每下载多少条保存一次
        """
        logger.info(f"Starting TikTok-10M download via API...")
        logger.info(f"Target samples: {max_samples}")

        output_file = self.output_dir / "tiktok-10m-sample.jsonl"
        all_data = []
        offset = 0

        with tqdm(total=max_samples, desc="Downloading") as pbar:
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
                    response.raise_for_status()

                    # 解析响应
                    data = response.json()

                    if "rows" not in data:
                        logger.error(f"Unexpected response format: {data}")
                        break

                    rows = data["rows"]
                    if not rows:
                        logger.info("No more data available")
                        break

                    # 提取数据
                    for row in rows:
                        record = row.get("row", {})
                        all_data.append(record)

                    # 更新进度
                    offset += len(rows)
                    pbar.update(len(rows))

                    # 定期保存
                    if len(all_data) % save_every == 0:
                        self._save_jsonl(all_data, output_file)
                        logger.info(f"Saved {len(all_data)} records to {output_file}")

                    # 避免请求过快
                    time.sleep(0.1)

                except requests.exceptions.RequestException as e:
                    logger.error(f"Request failed at offset {offset}: {e}")
                    logger.info("Retrying in 5 seconds...")
                    time.sleep(5)
                    continue

                except Exception as e:
                    logger.error(f"Error at offset {offset}: {e}")
                    break

        # 最终保存
        self._save_jsonl(all_data, output_file)
        logger.info(f"Download completed! Total records: {len(all_data)}")
        logger.info(f"Saved to: {output_file}")

        return output_file

    def _save_jsonl(self, data: List[Dict], output_file: Path):
        """保存为 JSONL 格式"""
        with open(output_file, "w", encoding="utf-8") as f:
            for record in data:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

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
    logger.info("TikTok-10M Dataset Downloader (API Version)")
    logger.info("=" * 60)

    downloader = HFDatasetDownloader(output_dir="D:/SalesBoost/data/raw")

    # 预览数据
    logger.info("\n[Step 1] Previewing data...")
    downloader.preview_data(limit=3)

    # 下载数据
    logger.info("\n[Step 2] Downloading data...")
    logger.info("Note: Downloading 10,000 samples for testing")
    logger.info("To download full dataset (10M), change max_samples parameter")

    output_file = downloader.download_tiktok_10m(
        batch_size=100,
        max_samples=10000,  # 先下载 1 万条测试
        save_every=1000
    )

    logger.info("\n" + "=" * 60)
    logger.info("Download completed!")
    logger.info("=" * 60)
    logger.info(f"Output file: {output_file}")
    logger.info("\nNext steps:")
    logger.info("1. Check the downloaded data")
    logger.info("2. Run preprocessing: python backend/scripts/preprocess_tiktok.py")
    logger.info("3. Train models: python backend/scripts/train_sft.py")


if __name__ == "__main__":
    main()
