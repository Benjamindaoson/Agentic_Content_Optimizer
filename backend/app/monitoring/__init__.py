"""
监控模块

生产环境监控系统
"""

from app.monitoring.production_monitor import (
    ProductionMonitor,
    DuplicationMonitor,
    EntropyMonitor,
    ExplorationMonitor,
    RewardDistributionMonitor,
    TopKStabilityMonitor
)
from typing import Optional

_MONITOR_SINGLETON: Optional[ProductionMonitor] = None


def get_production_monitor() -> ProductionMonitor:
    global _MONITOR_SINGLETON
    if _MONITOR_SINGLETON is None:
        _MONITOR_SINGLETON = ProductionMonitor()
    return _MONITOR_SINGLETON

__all__ = [
    'ProductionMonitor',
    'DuplicationMonitor',
    'EntropyMonitor',
    'ExplorationMonitor',
    'RewardDistributionMonitor',
    'TopKStabilityMonitor',
    'get_production_monitor',
]
