#!/usr/bin/env python3
"""
Growth Flywheel 最小可演示路径

端到端流程：
1. 输入 topic → 调用工作流生成内容
2. 获取 trace_id
3. 人工模拟反馈
4. 查询 stats

用法：
    python scripts/demo_flywheel.py [topic]
    python scripts/demo_flywheel.py "AI 提效工具推荐"

前置条件：docker-compose up 后，API 服务运行在 http://localhost:8000
"""

import argparse
import json
import os
import sys
from typing import Optional

# 禁用代理，确保 localhost 请求直达
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")

try:
    import requests
except ImportError:
    print("请安装 requests: pip install requests")
    sys.exit(1)

BASE_URL = os.getenv("FLYWHEEL_API_URL", "http://localhost:8000")


def generate_content(topic: str) -> Optional[dict]:
    """调用工作流生成内容，返回包含 trace_id 的响应"""
    url = f"{BASE_URL}/v1/workflow/generate/content"
    payload = {
        "topic": topic,
        "platform": "xiaohongshu",
        "goal_metric": "engagement",
    }
    print(f"\n📤 请求生成: topic={topic}")
    try:
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        if data.get("success"):
            trace_id = data.get("trace_id")
            score = data.get("final_score", 0)
            print(f"✅ 生成成功 | score={score:.2f} | trace_id={trace_id or '(无)'}")
            return data
        print(f"❌ 生成失败: {data.get('error', data)}")
        return None
    except requests.RequestException as e:
        print(f"❌ 请求失败: {e}")
        return None


def log_feedback(trace_id: str, impressions: int = 1000, likes: int = 50) -> bool:
    """模拟反馈"""
    url = f"{BASE_URL}/v1/ml/feedback/log"
    payload = {
        "trace_id": trace_id,
        "impressions": impressions,
        "clicks": 80,
        "read_time_avg": 45.0,
        "likes": likes,
        "comments": 10,
        "saves": 25,
        "shares": 5,
        "follows": 2,
    }
    print(f"\n📤 提交反馈: trace_id={trace_id}")
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "success":
            print(f"✅ 反馈记录成功 | outcome_id={data.get('outcome_id', '')}")
            return True
        print(f"❌ 反馈失败: {data}")
        return False
    except requests.RequestException as e:
        print(f"❌ 请求失败: {e}")
        return False


def get_stats() -> Optional[dict]:
    """查询反馈统计"""
    url = f"{BASE_URL}/v1/ml/feedback/stats"
    print("\n📤 查询 stats...")
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "success":
            stats = data.get("stats", {})
            print(f"✅ 统计: traces={stats.get('total_traces', 0)}, "
                  f"outcomes={stats.get('total_outcomes', 0)}, "
                  f"avg_engagement={stats.get('avg_engagement_score', 0):.4f}")
            return data
        print(f"❌ 查询失败: {data}")
        return None
    except requests.RequestException as e:
        print(f"❌ 请求失败: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Growth Flywheel 最小可演示路径")
    parser.add_argument(
        "topic",
        nargs="?",
        default="AI 提效工具推荐",
        help="内容主题",
    )
    parser.add_argument(
        "--skip-generate",
        action="store_true",
        help="跳过生成，仅用已有 trace_id 模拟反馈",
    )
    parser.add_argument(
        "--trace-id",
        type=str,
        help="指定 trace_id（与 --skip-generate 合用）",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Growth Flywheel 2.5 最小可演示路径")
    print("=" * 60)
    print(f"API: {BASE_URL}")

    trace_id = None
    if not args.skip_generate:
        result = generate_content(args.topic)
        if not result:
            sys.exit(1)
        trace_id = result.get("trace_id")
    elif args.trace_id:
        trace_id = args.trace_id
    else:
        print("❌ 使用 --skip-generate 时必须提供 --trace-id")
        sys.exit(1)

    if not trace_id:
        print("\n⚠️ 未获取到 trace_id，跳过反馈步骤")
        print("请检查生成接口是否返回 trace_id")
    else:
        log_feedback(trace_id)

    get_stats()
    print("\n" + "=" * 60)
    print("演示完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
