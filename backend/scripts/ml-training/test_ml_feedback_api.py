"""
测试 ML 反馈收集 API

验证:
1. 反馈记录 API
2. 平台数据记录 API
3. 统计查询 API
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
import json
import os

# Disable proxy for localhost
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
SESSION = requests.Session()
SESSION.proxies = {'http': None, 'https': None}

BASE_URL = "http://localhost:8001"


def test_log_feedback():
    """测试记录用户反馈"""
    print("\n" + "=" * 80)
    print("📝 测试记录用户反馈")
    print("=" * 80)

    # 首先需要一个 trace_id，使用测试数据中的
    # 从数据库获取一个 trace_id
    import sqlite3
    conn = sqlite3.connect("growth_flywheel.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM generation_traces LIMIT 1")
    result = cursor.fetchone()
    conn.close()

    if not result:
        print("❌ 没有找到 GenerationTrace，请先运行 test_ml_system_sqlite.py")
        return

    trace_id = result[0]
    print(f"使用 trace_id: {trace_id}")

    # 记录反馈
    payload = {
        "trace_id": trace_id,
        "impressions": 2000,
        "clicks": 100,
        "read_time_avg": 50.0,
        "likes": 40,
        "comments": 8,
        "saves": 25,
        "shares": 6,
        "follows": 2
    }

    response = SESSION.post(
        f"{BASE_URL}/api/ml/feedback/log",
        json=payload
    )

    print(f"\n状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")

    if response.status_code == 200:
        print("✅ 反馈记录成功")
    else:
        print("❌ 反馈记录失败")


def test_log_platform_data():
    """测试记录平台数据"""
    print("\n" + "=" * 80)
    print("📊 测试记录平台数据")
    print("=" * 80)

    # 获取 trace_id
    import sqlite3
    conn = sqlite3.connect("growth_flywheel.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM generation_traces LIMIT 1 OFFSET 1")
    result = cursor.fetchone()
    conn.close()

    if not result:
        print("⚠️  没有足够的 GenerationTrace")
        return

    trace_id = result[0]
    print(f"使用 trace_id: {trace_id}")

    # 记录平台数据
    payload = {
        "trace_id": trace_id,
        "platform_data": {
            "impressions": 1500,
            "clicks": 75,
            "read_time_avg": 42.0,
            "likes": 30,
            "comments": 5,
            "saves": 20,
            "shares": 4,
            "follows": 1
        }
    }

    response = SESSION.post(
        f"{BASE_URL}/api/ml/feedback/platform",
        json=payload
    )

    print(f"\n状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")

    if response.status_code == 200:
        print("✅ 平台数据记录成功")
    else:
        print("❌ 平台数据记录失败")


def test_get_stats():
    """测试获取统计"""
    print("\n" + "=" * 80)
    print("📈 测试获取统计")
    print("=" * 80)

    response = SESSION.get(f"{BASE_URL}/api/ml/feedback/stats")

    print(f"\n状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")

    if response.status_code == 200:
        stats = response.json()["stats"]
        print("\n📊 当前统计:")
        print(f"   - 总 Traces: {stats['total_traces']}")
        print(f"   - 总 Outcomes: {stats['total_outcomes']}")
        print(f"   - 平均互动分: {stats['avg_engagement_score']}")
        print(f"   - 可以开始 SFT: {'✅' if stats['ready_for_sft'] else '❌'}")
        print(f"   - 可以开始 DPO: {'✅' if stats['ready_for_dpo'] else '❌'}")
        print("✅ 统计查询成功")
    else:
        print("❌ 统计查询失败")


def main():
    """运行所有测试"""
    print("=" * 80)
    print("🧪 ML 反馈收集 API 测试")
    print("=" * 80)

    print("\n⚠️  请确保 API 服务已启动:")
    print("   uvicorn app.main:app --reload")
    print("\n按 Enter 继续...")
    input()

    try:
        # 测试 1: 记录用户反馈
        test_log_feedback()

        # 测试 2: 记录平台数据
        test_log_platform_data()

        # 测试 3: 获取统计
        test_get_stats()

        print("\n" + "=" * 80)
        print("✅ 所有测试完成！")
        print("=" * 80)

    except requests.exceptions.ConnectionError:
        print("\n❌ 无法连接到 API 服务")
        print("请先启动服务: uvicorn app.main:app --reload")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")


if __name__ == "__main__":
    main()
