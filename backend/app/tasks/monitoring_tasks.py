"""监控告警任务。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from app.monitoring import get_production_monitor

logger = logging.getLogger(__name__)


def _run_async(coro):
    try:
        with asyncio.Runner() as runner:
            return runner.run(coro)
    except AttributeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


async def _dispatch_alerts() -> Dict[str, Any]:
    monitor = get_production_monitor()
    return monitor.dispatch_alerts(total_possible_actions=400)


def dispatch_monitor_alerts_task() -> Dict[str, Any]:
    """派发监控告警到 Slack/PagerDuty。"""
    try:
        result = _run_async(_dispatch_alerts())
        logger.info(f"[MONITOR ALERT TASK] {result}")
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"[MONITOR ALERT TASK] Failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

