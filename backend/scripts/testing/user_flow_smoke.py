"""
用户链路烟测：
1) 启动临时服务
2) 健康检查
3) 注册/登录/获取用户信息
4) 尝试内容生成（可选）
5) 输出结构化报告
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests


def _spawn_server(project_root: Path, host: str, port: int) -> tuple[subprocess.Popen, list[str]]:
    env = os.environ.copy()
    env.setdefault(
        "DATABASE_URL",
        "postgresql://growth_user:GrowthFlywheel2025!Secure@127.0.0.1:5432/growth_flywheel",
    )
    env.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")
    env.setdefault("PYTHONUNBUFFERED", "1")

    cmd = ["uvicorn", "app.main:app", "--host", host, "--port", str(port)]
    proc = subprocess.Popen(
        cmd,
        cwd=str(project_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    lines: list[str] = []

    def _reader():
        if proc.stdout is None:
            return
        for line in proc.stdout:
            lines.append(line.rstrip("\n"))

    threading.Thread(target=_reader, daemon=True).start()
    return proc, lines


def _wait_ready(session: requests.Session, base_url: str, timeout_sec: int = 180) -> tuple[bool, dict]:
    deadline = time.time() + timeout_sec
    last_err = None
    while time.time() < deadline:
        try:
            r = session.get(f"{base_url}/health/ready", timeout=2)
            if r.status_code == 200:
                return True, r.json()
            last_err = f"status={r.status_code}"
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
        time.sleep(1)
    return False, {"error": last_err or "ready timeout"}


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    host = "127.0.0.1"
    port = 8012
    base_url = f"http://{host}:{port}"

    report = {
        "base_url": base_url,
        "checks": {},
        "overall_pass": False,
    }
    session = requests.Session()
    session.trust_env = False

    proc, logs = _spawn_server(project_root, host, port)
    try:
        ready_ok, ready_data = _wait_ready(session, base_url, timeout_sec=180)
        report["checks"]["ready"] = {"pass": ready_ok, "detail": ready_data}
        if not ready_ok:
            report["checks"]["startup_logs_tail"] = logs[-60:]
            print(json.dumps(report, ensure_ascii=True, indent=2))
            return 2

        # health/live
        live = session.get(f"{base_url}/health/live", timeout=5)
        report["checks"]["live"] = {"pass": live.status_code == 200, "status_code": live.status_code}

        # register/login/me
        ts = int(time.time())
        email = f"smoke_{ts}@example.com"
        password = "SmokeTestPass_123456"
        register_payload = {"email": email, "password": password, "full_name": "Smoke Tester"}
        reg = session.post(f"{base_url}/api/v1/auth/register", json=register_payload, timeout=10)
        reg_ok = reg.status_code in (200, 201)
        report["checks"]["register"] = {"pass": reg_ok, "status_code": reg.status_code, "body": reg.text[:400]}

        login = session.post(
            f"{base_url}/api/v1/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
        token = None
        try:
            token = login.json().get("data", {}).get("access_token")
        except Exception:  # noqa: BLE001
            token = None
        login_ok = login.status_code == 200 and bool(token)
        report["checks"]["login"] = {"pass": login_ok, "status_code": login.status_code}

        me_ok = False
        if token:
            me = session.get(
                f"{base_url}/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            me_ok = me.status_code == 200
            report["checks"]["me"] = {"pass": me_ok, "status_code": me.status_code}
        else:
            report["checks"]["me"] = {"pass": False, "status_code": None}

        # workflow generate (best-effort)
        wf_ok = False
        wf_status = None
        if token:
            payload = {
                "topic": "美国硕士申请时间线",
                "platform": "xiaohongshu",
                "agent_mode": "writer_only",
                "quality_threshold": 60,
                "llm_provider": "deepseek",
                "llm_model": "deepseek-v3.2",
                "max_refinement_loops": 1,
                "rag_mode": "adaptive",
            }
            try:
                wf = session.post(
                    f"{base_url}/v1/workflow/generate/content",
                    headers={"Authorization": f"Bearer {token}"},
                    json=payload,
                    timeout=90,
                )
                wf_status = wf.status_code
                wf_ok = wf.status_code == 200 and bool(wf.json().get("final_content"))
            except Exception as exc:  # noqa: BLE001
                wf_status = str(exc)
        report["checks"]["workflow_generate"] = {"pass": wf_ok, "status": wf_status}

        hard_pass = all(
            [
                report["checks"]["ready"]["pass"],
                report["checks"]["live"]["pass"],
                report["checks"]["register"]["pass"],
                report["checks"]["login"]["pass"],
                report["checks"]["me"]["pass"],
            ]
        )
        report["overall_pass"] = hard_pass
        report["workflow_optional_pass"] = wf_ok
        report["startup_logs_tail"] = logs[-40:]

        print(json.dumps(report, ensure_ascii=True, indent=2))
        return 0 if hard_pass else 3
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
