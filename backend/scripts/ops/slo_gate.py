"""
SLO 门禁脚本：
1) 检查 /health/ready
2) 执行轻量压测并按阈值验收
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import httpx


async def check_ready(base_url: str, timeout_sec: float) -> tuple[bool, dict[str, Any]]:
    url = base_url.rstrip("/") + "/health/ready"
    try:
        async with httpx.AsyncClient(timeout=timeout_sec, trust_env=False) as client:
            resp = await client.get(url)
            data = resp.json() if "application/json" in resp.headers.get("content-type", "") else {"raw": resp.text}
            return resp.status_code == 200, {"status_code": resp.status_code, "data": data}
    except Exception as exc:  # noqa: BLE001
        return False, {"error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description="SLO 验收门禁")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout-sec", type=float, default=3.0)
    parser.add_argument("--output-json", default="results/slo_gate.json")
    parser.add_argument("--endpoint", default="/health/live")
    parser.add_argument("--duration-sec", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--qps-per-worker", type=float, default=2.0)
    parser.add_argument("--max-p95-ms", type=float, default=800.0)
    parser.add_argument("--min-success-rate", type=float, default=0.995)
    args = parser.parse_args()

    ready_ok, ready_result = asyncio.run(check_ready(args.base_url, args.timeout_sec))

    load_cmd = [
        sys.executable,
        os.path.join(os.path.dirname(__file__), "load_test.py"),
        "--base-url",
        args.base_url,
        "--endpoint",
        args.endpoint,
        "--duration-sec",
        str(args.duration_sec),
        "--concurrency",
        str(args.concurrency),
        "--qps-per-worker",
        str(args.qps_per_worker),
        "--max-p95-ms",
        str(args.max_p95_ms),
        "--min-success-rate",
        str(args.min_success_rate),
    ]
    load_proc = subprocess.run(load_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    load_exit = load_proc.returncode

    report = {
        "ready": {
            "pass": ready_ok,
            "detail": ready_result,
        },
        "load_gate_exit_code": load_exit,
        "load_gate_stdout_tail": (load_proc.stdout or "")[-2000:],
        "load_gate_stderr_tail": (load_proc.stderr or "")[-1000:],
        "pass": ready_ok and load_exit == 0,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.output_json:
        out_path = Path(args.output_json)
        if not out_path.is_absolute():
            out_path = Path.cwd() / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    return 0 if report["pass"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
