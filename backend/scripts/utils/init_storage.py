#!/usr/bin/env python3
"""
初始化存储和向量数据库
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from minio import Minio
from minio.error import S3Error
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams


def init_minio():
    """初始化 MinIO 存储桶"""
    print("正在初始化 MinIO...")

    minio_client = Minio(
        os.getenv('MINIO_ENDPOINT', 'minio:9000'),
        access_key=os.getenv('MINIO_ACCESS_KEY', 'growth-app'),
        secret_key=os.getenv('MINIO_SECRET_KEY', 'GrowthApp2025!MinIOKey'),
        secure=False
    )

    buckets = ['covers', 'videos', 'exports', 'temp']

    for bucket in buckets:
        try:
            if not minio_client.bucket_exists(bucket):
                minio_client.make_bucket(bucket)
                print(f"✓ 创建存储桶: {bucket}")
            else:
                print(f"✓ 存储桶已存在: {bucket}")
        except S3Error as e:
            print(f"✗ 创建存储桶 {bucket} 失败: {e}")

    print("MinIO 初始化完成\n")


def init_qdrant():
    """初始化 Qdrant 向量集合"""
    print("正在初始化 Qdrant...")

    qdrant_client = QdrantClient(
        host=os.getenv('QDRANT_HOST', 'qdrant'),
        port=int(os.getenv('QDRANT_PORT', '6333'))
    )

    collections = {
        'topics': {
            'vector_size': 1536,  # OpenAI embedding size
            'distance': Distance.COSINE
        },
        'content': {
            'vector_size': 1536,
            'distance': Distance.COSINE
        },
        'covers': {
            'vector_size': 512,  # CLIP embedding size
            'distance': Distance.COSINE
        }
    }

    for collection_name, config in collections.items():
        try:
            existing_collections = qdrant_client.get_collections().collections
            if collection_name not in [c.name for c in existing_collections]:
                qdrant_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=config['vector_size'],
                        distance=config['distance']
                    )
                )
                print(f"✓ 创建集合: {collection_name}")
            else:
                print(f"✓ 集合已存在: {collection_name}")
        except Exception as e:
            print(f"✗ 创建集合 {collection_name} 失败: {e}")

    print("Qdrant 初始化完成\n")


def main():
    """主函数"""
    print("=" * 50)
    print("Growth Flywheel v4.0 - 存储初始化")
    print("=" * 50)
    print()

    try:
        init_minio()
        init_qdrant()

        print("=" * 50)
        print("✓ 所有存储初始化完成!")
        print("=" * 50)
        return 0
    except Exception as e:
        print(f"\n✗ 初始化失败: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
