"""
轻量压测脚本（异步 httpx）。

用途：
1) 快速评估接口吞吐与延迟（p50/p95/p99）
2) 作为 SLO 门禁（支持阈值参数）
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import time
from dataclasses import dataclass, asdict
from typing import Any, Optional

import httpx


@dataclass
class RequestResult:
    ok: bool
    status_code: int
    latency_ms: float
    error: Optional[str] = None


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if p <= 0:
        return min(values)
    if p >= 100:
        return max(values)
    sorted_vals = sorted(values)
    idx = (len(sorted_vals) - 1) * (p / 100.0)
    lower = math.floor(idx)
    upper = math.ceil(idx)
    if lower == upper:
        return sorted_vals[lower]
    ratio = idx - lower
    return sorted_vals[lower] * (1 - ratio) + sorted_vals[upper] * ratio


async def one_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    body: Any | None,
) -> RequestResult:
    started = time.perf_counter()
    try:
        if method == "GET":
            resp = await client.get(url)
        else:
            resp = await client.post(url, json=body)
        latency_ms = (time.perf_counter() - started) * 1000
        return RequestResult(
            ok=200 <= resp.status_code < 400,
            status_code=resp.status_code,
            latency_ms=latency_ms,
        )
    except Exception as exc:  # noqa: BLE001
        latency_ms = (time.perf_counter() - started) * 1000
        return RequestResult(
            ok=False,
            status_code=0,
            latency_ms=latency_ms,
            error=str(exc),
        )


async def worker(
    worker_id: int,
    client: httpx.AsyncClient,
    method: str,
    url: str,
    body: Any | None,
    duration_sec: int,
    qps_per_worker: float,
    out: list[RequestResult],
):
    _ = worker_id
    interval = (1.0 / qps_per_worker) if qps_per_worker > 0 else 0.0
    deadline = time.perf_counter() + duration_sec
    while time.perf_counter() < deadline:
        out.append(await one_request(client, method, url, body))
        if interval > 0:
            await asyncio.sleep(interval)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="HTTP 接口压测与 SLO 门禁")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--endpoint", default="/health/live")
    parser.add_argument("--method", choices=["GET", "POST"], default="GET")
    parser.add_argument("--duration-sec", type=int, default=30)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--qps-per-worker", type=float, default=2.0)
    parser.add_argument("--timeout-sec", type=float, default=10.0)
    parser.add_argument("--bearer-token", default=None)
    parser.add_argument("--body-json", default=None, help="POST JSON 字符串")
    parser.add_argument("--body-file", default=None, help="POST JSON 文件路径")
    parser.add_argument("--max-p95-ms", type=float, default=1200.0)
    parser.add_argument("--min-success-rate", type=float, default=0.99)
    parser.add_argument("--output-json", default=None)
    return parser


async def run(args: argparse.Namespace) -> int:
    url = args.base_url.rstrip("/") + "/" + args.endpoint.lstrip("/")
    body = None
    if args.body_file:
        with open(args.body_file, "r", encoding="utf-8") as f:
            body = json.load(f)
    elif args.body_json:
        body = json.loads(args.body_json)

    headers = {}
    if args.bearer_token:
        headers["Authorization"] = f"Bearer {args.bearer_token}"

    limits = httpx.Limits(max_keepalive_connections=args.concurrency * 2, max_connections=args.concurrency * 4)
    timeout = httpx.Timeout(timeout=args.timeout_sec)
    results: list[RequestResult] = []

    started = time.perf_counter()
    async with httpx.AsyncClient(headers=headers, limits=limits, timeout=timeout, trust_env=False) as client:
        tasks = [
            worker(
                worker_id=i,
                client=client,
                method=args.method,
                url=url,
                body=body,
                duration_sec=args.duration_sec,
                qps_per_worker=args.qps_per_worker,
                out=results,
            )
            for i in range(args.concurrency)
        ]
        await asyncio.gather(*tasks)
    elapsed = max(time.perf_counter() - started, 0.001)

    latencies = [r.latency_ms for r in results]
    success_count = sum(1 for r in results if r.ok)
    failure_count = len(results) - success_count
    success_rate = (success_count / len(results)) if results else 0.0
    rps = len(results) / elapsed

    report = {
        "url": url,
        "method": args.method,
        "duration_sec": args.duration_sec,
        "concurrency": args.concurrency,
        "qps_per_worker": args.qps_per_worker,
        "requests_total": len(results),
        "success_count": success_count,
        "failure_count": failure_count,
        "success_rate": round(success_rate, 6),
        "rps": round(rps, 3),
        "latency_ms": {
            "avg": round(statistics.mean(latencies), 3) if latencies else 0.0,
            "p50": round(percentile(latencies, 50), 3),
            "p95": round(percentile(latencies, 95), 3),
            "p99": round(percentile(latencies, 99), 3),
            "max": round(max(latencies), 3) if latencies else 0.0,
        },
        "failed_samples": [asdict(r) for r in results if not r.ok][:10],
        "thresholds": {
            "max_p95_ms": args.max_p95_ms,
            "min_success_rate": args.min_success_rate,
        },
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    pass_gate = (
        report["latency_ms"]["p95"] <= args.max_p95_ms
        and report["success_rate"] >= args.min_success_rate
    )
    return 0 if pass_gate else 2


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
