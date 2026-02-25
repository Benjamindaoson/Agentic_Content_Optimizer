"""告警通知器（Slack / PagerDuty）。"""

from __future__ import annotations

import logging
from typing import Iterable

import requests

from app.core.config import get_settings

logger = logging.getLogger(__name__)

LEVEL_ORDER = {"INFO": 1, "WARNING": 2, "CRITICAL": 3}


def _extract_level(alert: str) -> str:
    prefix = (alert.split(":", 1)[0] or "").strip().upper()
    return prefix if prefix in LEVEL_ORDER else "WARNING"


class AlertNotifier:
    def __init__(self):
        self.settings = get_settings()

    def _enabled(self) -> bool:
        return bool(self.settings.ALERT_SLACK_WEBHOOK_URL or self.settings.ALERT_PAGERDUTY_ROUTING_KEY)

    def _allow(self, level: str) -> bool:
        min_level = str(self.settings.ALERT_MIN_LEVEL or "WARNING").upper()
        return LEVEL_ORDER.get(level, 2) >= LEVEL_ORDER.get(min_level, 2)

    def notify(self, alerts: Iterable[str]) -> dict:
        alerts = list(alerts)
        if not alerts:
            return {"sent": 0, "skipped": 0}
        if not self._enabled():
            logger.info("Alert notifier disabled: no webhook configured")
            return {"sent": 0, "skipped": len(alerts)}

        sent = 0
        skipped = 0
        for alert in alerts:
            level = _extract_level(alert)
            if not self._allow(level):
                skipped += 1
                continue
            if self.settings.ALERT_SLACK_WEBHOOK_URL:
                self._send_slack(level, alert)
            if self.settings.ALERT_PAGERDUTY_ROUTING_KEY:
                self._send_pagerduty(level, alert)
            sent += 1
        return {"sent": sent, "skipped": skipped}

    def _send_slack(self, level: str, alert: str):
        payload = {
            "text": f"[{level}] Growth Flywheel Alert\n{alert}",
        }
        try:
            requests.post(
                self.settings.ALERT_SLACK_WEBHOOK_URL,
                json=payload,
                timeout=5,
            ).raise_for_status()
        except Exception as e:
            logger.warning(f"Slack alert failed: {e}")

    def _send_pagerduty(self, level: str, alert: str):
        severity = "critical" if level == "CRITICAL" else "warning"
        payload = {
            "routing_key": self.settings.ALERT_PAGERDUTY_ROUTING_KEY,
            "event_action": "trigger",
            "payload": {
                "summary": alert,
                "source": "growth-flywheel",
                "severity": severity,
            },
        }
        try:
            requests.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload,
                timeout=5,
            ).raise_for_status()
        except Exception as e:
            logger.warning(f"PagerDuty alert failed: {e}")

