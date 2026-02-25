"""
测试内容生成 + ML 日志记录集成

验证:
1. 内容生成 API 正常工作
2. ML 日志自动记录
3. trace_id 正确返回
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
import json
import os
import sqlite3

# Disable proxy for localhost
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
SESSION = requests.Session()
SESSION.proxies = {'http': None, 'https': None}

BASE_URL = "http://localhost:8000"  # 使用主 API


def test_content_generation_with_logging():
    """测试内容生成 + ML 日志记录"""
    print("\n" + "=" * 80)
    print("📝 测试内容生成 + ML 日志记录")
    print("=" * 80)

    # 获取生成前的 trace 数量
    conn = sqlite3.connect("growth_flywheel.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM generation_traces")
    before_count = cursor.fetchone()[0]
    conn.close()

    print(f"\n生成前 GenerationTrace 数量: {before_count}")

    # 调用内容生成 API
    payload = {
        "category": "科技",
        "topic": "AI 写作助手",
        "target_audience": "内容创作者",
        "style_preference": "专业",
        "num_candidates": 3,
        "llm_provider": "dots"
    }

    print(f"\n请求参数: {json.dumps(payload, ensure_ascii=False, indent=2)}")

    try:
        response = SESSION.post(
            f"{BASE_URL}/api/generate/content",
            json=payload,
            timeout=30
        )

        print(f"\n状态码: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"\n响应: {json.dumps(result, ensure_ascii=False, indent=2)}")

            # 检查 trace_id
            trace_id = result.get("trace_id")
            if trace_id:
                print(f"\n✅ trace_id 已返回: {trace_id}")

                # 验证数据库中是否有新记录
                conn = sqlite3.connect("growth_flywheel.db")
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM generation_traces")
                after_count = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT platform, topic, category FROM generation_traces WHERE id = ?",
                    (trace_id,)
                )
                trace = cursor.fetchone()
                conn.close()

                print(f"生成后 GenerationTrace 数量: {after_count}")

                if after_count > before_count:
                    print("✅ ML 日志记录成功")
                    if trace:
                        print(f"   - Platform: {trace[0]}")
                        print(f"   - Topic: {trace[1]}")
                        print(f"   - Category: {trace[2]}")
                else:
                    print("❌ ML 日志记录失败")
            else:
                print("⚠️  trace_id 未返回")

            print(f"\n生成了 {result.get('total', 0)} 个候选内容")
        else:
            print(f"❌ 请求失败: {response.text}")

    except requests.exceptions.ConnectionError:
        print("\n❌ 无法连接到 API 服务")
        print("请先启动服务: uvicorn app.main:app --reload")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")


def main():
    """运行测试"""
    print("=" * 80)
    print("🧪 内容生成 + ML 日志记录集成测试")
    print("=" * 80)

    print("\n⚠️  请确保主 API 服务已启动:")
    print("   uvicorn app.main:app --reload")
    print("\n按 Enter 继续...")
    input()

    test_content_generation_with_logging()

    print("\n" + "=" * 80)
    print("✅ 测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    main()
