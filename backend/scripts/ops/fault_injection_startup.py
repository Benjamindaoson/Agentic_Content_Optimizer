"""
启动链路故障注入脚本。

场景：
1) Redis 不可用
2) Postgres 不可用

期望：
- 主服务在硬依赖异常时快速失败（而不是长时间卡住）
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from urllib import error as urlerror
from urllib import request as urlrequest


@dataclass
class Scenario:
    name: str
    env_overrides: dict[str, str]
    expect_fail_fast: bool = True


def run_scenario(s: Scenario, startup_timeout_sec: int) -> dict:
    env = os.environ.copy()
    env.update(s.env_overrides)
    env.setdefault("PYTHONUNBUFFERED", "1")

    cmd = [
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8019",
    ]

    started = time.time()
    proc = subprocess.Popen(
        cmd,
        cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    output_lines: list[str] = []
    saw_startup_complete = False
    stream_done = False

    def _consume_stdout():
        nonlocal saw_startup_complete, stream_done
        if not proc.stdout:
            stream_done = True
            return
        for line in proc.stdout:
            text = line.rstrip("\n")
            output_lines.append(text)
            if "Application startup complete" in text:
                saw_startup_complete = True
        stream_done = True

    t = threading.Thread(target=_consume_stdout, daemon=True)
    t.start()

    exited = False
    exit_code = None
    ready_seen = False
    ready_status_code = None

    def _probe_ready() -> tuple[bool, int | None]:
        url = "http://127.0.0.1:8019/health/ready"
        opener = urlrequest.build_opener(urlrequest.ProxyHandler({}))
        try:
            with opener.open(url, timeout=0.8) as resp:  # nosec B310
                return resp.status == 200, resp.status
        except urlerror.HTTPError as he:
            return False, he.code
        except Exception:
            return False, None

    try:
        while time.time() - started < startup_timeout_sec:
            exit_code = proc.poll()
            if exit_code is not None:
                exited = True
                break
            ok, code = _probe_ready()
            if code is not None:
                ready_status_code = code
            if ok:
                ready_seen = True
                break
            time.sleep(0.3)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        t.join(timeout=1.0)

    elapsed = round(time.time() - started, 3)
    fail_fast = exited and (exit_code or 0) != 0 and not ready_seen
    if s.expect_fail_fast:
        passed = fail_fast
        if ready_seen:
            reason = "service_became_ready_unexpectedly"
        elif exited and (exit_code or 0) == 0:
            reason = "process_exited_zero_unexpectedly"
        elif not exited:
            reason = "startup_hang_or_no_fail_fast"
        else:
            reason = "fail_fast_as_expected"
    else:
        passed = True
        reason = "not_checked"

    return {
        "scenario": s.name,
        "elapsed_sec": elapsed,
        "process_exited": exited,
        "exit_code": exit_code,
        "ready_seen": ready_seen,
        "ready_status_code": ready_status_code,
        "saw_startup_complete_log": saw_startup_complete,
        "stdout_stream_done": stream_done,
        "expect_fail_fast": s.expect_fail_fast,
        "reason": reason,
        "pass": passed,
        "logs_tail": output_lines[-25:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="启动故障注入检查")
    parser.add_argument("--startup-timeout-sec", type=int, default=25)
    parser.add_argument("--output-json", default="results/ops_gate.json")
    args = parser.parse_args()

    scenarios = [
        Scenario(
            name="redis_unreachable",
            env_overrides={"REDIS_URL": "redis://127.0.0.1:6399/0"},
        ),
        Scenario(
            name="postgres_unreachable",
            env_overrides={"DATABASE_URL": "postgresql://bad:bad@127.0.0.1:6543/not_exists"},
        ),
    ]

    results = [run_scenario(s, args.startup_timeout_sec) for s in scenarios]
    report = {
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r["pass"]),
            "failed": sum(1 for r in results if not r["pass"]),
        },
        "results": results,
    }

    print(json.dumps(report, ensure_ascii=True, indent=2))
    if args.output_json:
        out_path = Path(args.output_json)
        if not out_path.is_absolute():
            out_path = Path.cwd() / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    return 0 if report["summary"]["failed"] == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
