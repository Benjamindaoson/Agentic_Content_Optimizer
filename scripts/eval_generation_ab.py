#!/usr/bin/env python3
"""
Phase 2: 生成对比 A/B 评估

同一批 topic：基线 vs 当前系统，记录质量分、token、延迟。

用法：
    python scripts/eval_generation_ab.py [--topics scripts/eval_topics.json]
    python scripts/eval_generation_ab.py --topic "AI 提效工具推荐"
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")

project_root = Path(__file__).resolve().parent.parent
backend_dir = project_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    import requests
except ImportError:
    print("请安装 requests: pip install requests")
    sys.exit(1)

BASE_URL = os.getenv("FLYWHEEL_API_URL", "http://localhost:8000")


def load_topics(path: str) -> List[Dict[str, str]]:
    """从 JSON 加载 topic 列表"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "topics" in data:
        return data["topics"]
    return [{"topic": str(data), "platform": "xiaohongshu"}]


async def run_baseline(topic: str, platform: str = "xiaohongshu") -> Dict[str, Any]:
    """运行基线（复用 eval_baseline 逻辑）"""
    try:
        from scripts.eval_baseline import run_baseline as _run
        return await _run(topic=topic, platform=platform, evaluate=True)
    except ImportError:
        # 从 eval_baseline 模块加载（可能路径不同）
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "eval_baseline",
            project_root / "scripts" / "eval_baseline.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return await mod.run_baseline(topic=topic, platform=platform, evaluate=True)


def run_current_system(topic: str, platform: str = "xiaohongshu") -> Dict[str, Any]:
    """调用当前系统（Workflow API）"""
    url = f"{BASE_URL}/v1/workflow/generate/content"
    payload = {"topic": topic, "platform": platform, "goal_metric": "engagement"}
    start = time.perf_counter()
    try:
        resp = requests.post(url, json=payload, timeout=180)
        latency_ms = int((time.perf_counter() - start) * 1000)
        data = resp.json()
        if not data.get("success"):
            return {
                "topic": topic,
                "success": False,
                "error": data.get("error", resp.text),
                "latency_ms": latency_ms,
                "quality_score": None,
                "token_count_est": None,
            }
        content = data.get("final_content", {})
        text = ""
        ts = content.get("text_structure", {})
        if ts:
            text = ts.get("full_text", "") or str(ts)
        else:
            text = str(content)
        token_est = max(1, len(text) // 2) if text else 0
        score = data.get("final_score")
        return {
            "topic": topic,
            "success": True,
            "latency_ms": latency_ms,
            "quality_score": float(score) if score is not None else None,
            "token_count_est": token_est,
            "iterations": data.get("iterations", 0),
        }
    except Exception as e:
        return {
            "topic": topic,
            "success": False,
            "error": str(e),
            "latency_ms": int((time.perf_counter() - start) * 1000),
            "quality_score": None,
            "token_count_est": None,
        }


async def main():
    parser = argparse.ArgumentParser(description="Phase 2: 生成对比 A/B")
    parser.add_argument("--topic", type=str, help="单个 topic")
    parser.add_argument("--topics", type=str, default="scripts/eval_topics.json")
    parser.add_argument("--output", type=str, default="results/eval_ab.json")
    parser.add_argument("--skip-baseline", action="store_true", help="跳过基线（仅跑当前系统）")
    parser.add_argument("--skip-current", action="store_true", help="跳过当前系统（仅跑基线）")
    args = parser.parse_args()

    if args.topic:
        topics = [{"topic": args.topic, "platform": "xiaohongshu"}]
    else:
        topics_path = project_root / args.topics
        if not topics_path.exists():
            topics = [
                {"topic": "AI 提效工具推荐", "platform": "xiaohongshu"},
                {"topic": "如何提高工作效率", "platform": "xiaohongshu"},
            ]
        else:
            topics = load_topics(str(topics_path))

    print("=" * 60)
    print("Phase 2: 生成对比 A/B（基线 vs 当前系统）")
    print("=" * 60)
    print(f"Topics: {len(topics)}")
    print(f"API: {BASE_URL}")

    baseline_results = []
    current_results = []

    for i, t in enumerate(topics):
        topic = t.get("topic", t) if isinstance(t, dict) else t
        platform = t.get("platform", "xiaohongshu") if isinstance(t, dict) else "xiaohongshu"
        print(f"\n[{i+1}/{len(topics)}] {topic}")

        if not args.skip_baseline:
            print("  Running baseline...")
            b = await run_baseline(topic, platform)
            baseline_results.append(b)
            print(f"    latency={b['latency_ms']}ms, quality={b.get('quality_score')}")

        if not args.skip_current:
            print("  Running current system...")
            c = run_current_system(topic, platform)
            current_results.append(c)
            print(f"    latency={c['latency_ms']}ms, quality={c.get('quality_score')}")

    # 汇总对比
    def avg(lst, key):
        vals = [x[key] for x in lst if x.get(key) is not None]
        return sum(vals) / len(vals) if vals else None

    def p95(lst, key):
        vals = [x[key] for x in lst if x.get(key) is not None]
        if not vals:
            return None
        s = sorted(vals)
        return s[min(int(len(s) * 0.95), len(s) - 1)]

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "num_topics": len(topics),
        "baseline": {
            "results": baseline_results,
            "avg_quality": avg(baseline_results, "quality_score"),
            "avg_latency_ms": avg(baseline_results, "latency_ms"),
            "avg_tokens": avg(baseline_results, "total_tokens_est"),
            "p95_latency_ms": p95(baseline_results, "latency_ms"),
        } if baseline_results else {},
        "current_system": {
            "results": current_results,
            "avg_quality": avg(current_results, "quality_score"),
            "avg_latency_ms": avg(current_results, "latency_ms"),
            "avg_tokens": avg(current_results, "token_count_est"),
            "p95_latency_ms": p95(current_results, "latency_ms"),
        } if current_results else {},
    }

    # 计算提升
    if baseline_results and current_results:
        bq = report["baseline"].get("avg_quality")
        cq = report["current_system"].get("avg_quality")
        bl = report["baseline"].get("avg_latency_ms")
        cl = report["current_system"].get("avg_latency_ms")
        if bq and cq:
            report["quality_delta"] = round((cq - bq) / bq * 100, 2) if bq else None
        if bl and cl:
            report["latency_delta_pct"] = round((cl - bl) / bl * 100, 2) if bl else None

    print("\n" + "=" * 60)
    print("Summary:")
    print(json.dumps({k: v for k, v in report.items() if k != "baseline" and k != "current_system" or k == "quality_delta" or k == "latency_delta_pct"}, indent=2, default=str))
    if "baseline" in report and report["baseline"]:
        print("Baseline avg:", report["baseline"].get("avg_quality"), report["baseline"].get("avg_latency_ms"))
    if "current_system" in report and report["current_system"]:
        print("Current avg:", report["current_system"].get("avg_quality"), report["current_system"].get("avg_latency_ms"))
    print("=" * 60)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print(f"Saved to {out_path}")

    return report


if __name__ == "__main__":
    asyncio.run(main())
