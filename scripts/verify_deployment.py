#!/usr/bin/env python3
"""
部署验证脚本 - 检查所有服务状态
"""
import requests
import psycopg2
import redis
from qdrant_client import QdrantClient
import sys


def check_api():
    """检查 API 服务"""
    try:
        response = requests.get('http://localhost:8080/docs', timeout=5)
        if response.status_code == 200:
            print("✓ API 服务正常 (http://localhost:8080)")
            return True
        else:
            print(f"✗ API 服务异常: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ API 服务连接失败: {e}")
        return False


def check_postgres():
    """检查 PostgreSQL"""
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='growth_flywheel',
            user='growth_user',
            password='growth_password_2024'
        )
        cursor = conn.cursor()
        cursor.execute('SELECT version();')
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        print(f"✓ PostgreSQL 正常 (localhost:5432)")
        return True
    except Exception as e:
        print(f"✗ PostgreSQL 连接失败: {e}")
        return False


def check_redis():
    """检查 Redis"""
    try:
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        r.ping()
        print("✓ Redis 正常 (localhost:6379)")
        return True
    except Exception as e:
        print(f"✗ Redis 连接失败: {e}")
        return False


def check_qdrant():
    """检查 Qdrant"""
    try:
        client = QdrantClient(host='localhost', port=6333)
        collections = client.get_collections()
        print(f"✓ Qdrant 正常 (localhost:6333) - {len(collections.collections)} 个集合")
        return True
    except Exception as e:
        print(f"✗ Qdrant 连接失败: {e}")
        return False


def check_minio():
    """检查 MinIO"""
    try:
        response = requests.get('http://localhost:9001/minio/health/live', timeout=5)
        if response.status_code == 200:
            print("✓ MinIO 正常 (http://localhost:9001)")
            return True
        else:
            print(f"✗ MinIO 异常: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ MinIO 连接失败: {e}")
        return False


def check_prometheus():
    """检查 Prometheus"""
    try:
        response = requests.get('http://localhost:9090/-/healthy', timeout=5)
        if response.status_code == 200:
            print("✓ Prometheus 正常 (http://localhost:9090)")
            return True
        else:
            print(f"✗ Prometheus 异常: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Prometheus 连接失败: {e}")
        return False


def check_grafana():
    """检查 Grafana"""
    try:
        response = requests.get('http://localhost:3000/api/health', timeout=5)
        if response.status_code == 200:
            print("✓ Grafana 正常 (http://localhost:3000)")
            return True
        else:
            print(f"✗ Grafana 异常: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Grafana 连接失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("Growth Flywheel v4.0 - 部署验证")
    print("=" * 60)
    print()

    checks = [
        ("API 服务", check_api),
        ("PostgreSQL", check_postgres),
        ("Redis", check_redis),
        ("Qdrant", check_qdrant),
        ("MinIO", check_minio),
        ("Prometheus", check_prometheus),
        ("Grafana", check_grafana),
    ]

    results = []
    for name, check_func in checks:
        results.append(check_func())

    print()
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"验证结果: {passed}/{total} 项通过")

    if passed == total:
        print("✓ 所有服务运行正常!")
        print()
        print("访问地址:")
        print("  - API 文档: http://localhost:8080/docs")
        print("  - Grafana: http://localhost:3000 (admin/admin)")
        print("  - Prometheus: http://localhost:9090")
        print("  - MinIO: http://localhost:9001 (minioadmin/MinIO2025!Secure)")
    else:
        print(f"✗ {total - passed} 项服务异常,请检查日志")

    print("=" * 60)
    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())
