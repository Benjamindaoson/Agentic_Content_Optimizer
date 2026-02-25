"""
性能监控和优化

提供全面的性能监控：
1. 请求延迟追踪
2. 资源使用监控
3. 性能瓶颈识别
4. 自动优化建议
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import time
import psutil
import logging
from collections import deque
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """性能指标"""
    timestamp: datetime
    request_latency_ms: float
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    active_requests: int
    cache_hit_rate: float
    throughput_rps: float  # requests per second


@dataclass
class PerformanceAlert:
    """性能告警"""
    alert_type: str  # latency/cpu/memory/throughput
    severity: str  # warning/critical
    message: str
    value: float
    threshold: float
    timestamp: datetime
    suggestions: List[str] = field(default_factory=list)


class PerformanceMonitor:
    """
    性能监控器

    核心功能：
    1. 实时性能监控
    2. 性能指标收集
    3. 瓶颈识别
    4. 优化建议
    """

    def __init__(
        self,
        history_size: int = 1000,
        alert_thresholds: Optional[Dict[str, float]] = None
    ):
        """初始化性能监控器

        Args:
            history_size: 历史记录大小
            alert_thresholds: 告警阈值
        """
        self.history_size = history_size

        # 默认告警阈值
        self.alert_thresholds = alert_thresholds or {
            "latency_warning_ms": 1000,  # 1秒
            "latency_critical_ms": 3000,  # 3秒
            "cpu_warning_percent": 70,
            "cpu_critical_percent": 90,
            "memory_warning_percent": 70,
            "memory_critical_percent": 90,
            "throughput_warning_rps": 1,  # 低于1 RPS
        }

        # 性能历史
        self._metrics_history: deque = deque(maxlen=history_size)

        # 告警历史
        self._alerts: deque = deque(maxlen=100)

        # 当前活跃请求
        self._active_requests = 0

        # 请求计数（用于计算吞吐量）
        self._request_count = 0
        self._last_throughput_check = time.time()

        # 进程信息
        self._process = psutil.Process()

        logger.info("PerformanceMonitor initialized")

    def start_request(self) -> float:
        """开始请求追踪

        Returns:
            开始时间戳
        """
        self._active_requests += 1
        self._request_count += 1
        return time.time()

    def end_request(
        self,
        start_time: float,
        cache_hit: bool = False
    ) -> PerformanceMetrics:
        """结束请求追踪

        Args:
            start_time: 开始时间戳
            cache_hit: 是否命中缓存

        Returns:
            性能指标
        """
        self._active_requests = max(0, self._active_requests - 1)

        # 计算延迟
        latency_ms = (time.time() - start_time) * 1000

        # 收集系统指标
        cpu_percent = self._process.cpu_percent()
        memory_info = self._process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        memory_percent = self._process.memory_percent()

        # 计算吞吐量
        current_time = time.time()
        time_elapsed = current_time - self._last_throughput_check

        if time_elapsed >= 1.0:  # 每秒更新一次
            throughput_rps = self._request_count / time_elapsed
            self._request_count = 0
            self._last_throughput_check = current_time
        else:
            # 使用历史平均值
            if self._metrics_history:
                throughput_rps = sum(
                    m.throughput_rps for m in list(self._metrics_history)[-10:]
                ) / min(10, len(self._metrics_history))
            else:
                throughput_rps = 0.0

        # 创建指标
        metrics = PerformanceMetrics(
            timestamp=datetime.now(),
            request_latency_ms=latency_ms,
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_mb=memory_mb,
            active_requests=self._active_requests,
            cache_hit_rate=1.0 if cache_hit else 0.0,
            throughput_rps=throughput_rps
        )

        # 保存到历史
        self._metrics_history.append(metrics)

        # 检查告警
        self._check_alerts(metrics)

        return metrics

    def _check_alerts(self, metrics: PerformanceMetrics):
        """检查性能告警

        Args:
            metrics: 性能指标
        """
        alerts = []

        # 延迟告警
        if metrics.request_latency_ms > self.alert_thresholds["latency_critical_ms"]:
            alerts.append(PerformanceAlert(
                alert_type="latency",
                severity="critical",
                message=f"Request latency is critically high: {metrics.request_latency_ms:.0f}ms",
                value=metrics.request_latency_ms,
                threshold=self.alert_thresholds["latency_critical_ms"],
                timestamp=metrics.timestamp,
                suggestions=[
                    "Enable caching for frequently accessed data",
                    "Optimize database queries",
                    "Consider horizontal scaling",
                    "Review slow API calls"
                ]
            ))
        elif metrics.request_latency_ms > self.alert_thresholds["latency_warning_ms"]:
            alerts.append(PerformanceAlert(
                alert_type="latency",
                severity="warning",
                message=f"Request latency is high: {metrics.request_latency_ms:.0f}ms",
                value=metrics.request_latency_ms,
                threshold=self.alert_thresholds["latency_warning_ms"],
                timestamp=metrics.timestamp,
                suggestions=[
                    "Check cache hit rate",
                    "Profile slow operations"
                ]
            ))

        # CPU 告警
        if metrics.cpu_percent > self.alert_thresholds["cpu_critical_percent"]:
            alerts.append(PerformanceAlert(
                alert_type="cpu",
                severity="critical",
                message=f"CPU usage is critically high: {metrics.cpu_percent:.1f}%",
                value=metrics.cpu_percent,
                threshold=self.alert_thresholds["cpu_critical_percent"],
                timestamp=metrics.timestamp,
                suggestions=[
                    "Scale horizontally",
                    "Optimize CPU-intensive operations",
                    "Use async/await for I/O operations"
                ]
            ))
        elif metrics.cpu_percent > self.alert_thresholds["cpu_warning_percent"]:
            alerts.append(PerformanceAlert(
                alert_type="cpu",
                severity="warning",
                message=f"CPU usage is high: {metrics.cpu_percent:.1f}%",
                value=metrics.cpu_percent,
                threshold=self.alert_thresholds["cpu_warning_percent"],
                timestamp=metrics.timestamp,
                suggestions=["Monitor CPU usage trends"]
            ))

        # 内存告警
        if metrics.memory_percent > self.alert_thresholds["memory_critical_percent"]:
            alerts.append(PerformanceAlert(
                alert_type="memory",
                severity="critical",
                message=f"Memory usage is critically high: {metrics.memory_percent:.1f}% ({metrics.memory_mb:.0f}MB)",
                value=metrics.memory_percent,
                threshold=self.alert_thresholds["memory_critical_percent"],
                timestamp=metrics.timestamp,
                suggestions=[
                    "Clear caches",
                    "Check for memory leaks",
                    "Increase memory allocation",
                    "Optimize data structures"
                ]
            ))
        elif metrics.memory_percent > self.alert_thresholds["memory_warning_percent"]:
            alerts.append(PerformanceAlert(
                alert_type="memory",
                severity="warning",
                message=f"Memory usage is high: {metrics.memory_percent:.1f}% ({metrics.memory_mb:.0f}MB)",
                value=metrics.memory_percent,
                threshold=self.alert_thresholds["memory_warning_percent"],
                timestamp=metrics.timestamp,
                suggestions=["Monitor memory usage trends"]
            ))

        # 吞吐量告警
        if metrics.throughput_rps < self.alert_thresholds["throughput_warning_rps"]:
            alerts.append(PerformanceAlert(
                alert_type="throughput",
                severity="warning",
                message=f"Throughput is low: {metrics.throughput_rps:.2f} RPS",
                value=metrics.throughput_rps,
                threshold=self.alert_thresholds["throughput_warning_rps"],
                timestamp=metrics.timestamp,
                suggestions=[
                    "Check for bottlenecks",
                    "Optimize request handling"
                ]
            ))

        # 保存告警
        for alert in alerts:
            self._alerts.append(alert)
            logger.warning(f"Performance alert: {alert.message}")

    def get_current_metrics(self) -> Optional[PerformanceMetrics]:
        """获取当前性能指标

        Returns:
            最新的性能指标
        """
        if self._metrics_history:
            return self._metrics_history[-1]
        return None

    def get_metrics_summary(
        self,
        window_minutes: int = 5
    ) -> Dict[str, Any]:
        """获取性能指标摘要

        Args:
            window_minutes: 时间窗口（分钟）

        Returns:
            指标摘要
        """
        if not self._metrics_history:
            return {"status": "no_data"}

        # 过滤时间窗口内的指标
        cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
        recent_metrics = [
            m for m in self._metrics_history
            if m.timestamp >= cutoff_time
        ]

        if not recent_metrics:
            return {"status": "no_recent_data"}

        # 计算统计
        latencies = [m.request_latency_ms for m in recent_metrics]
        cpu_percents = [m.cpu_percent for m in recent_metrics]
        memory_percents = [m.memory_percent for m in recent_metrics]
        throughputs = [m.throughput_rps for m in recent_metrics]

        return {
            "window_minutes": window_minutes,
            "total_requests": len(recent_metrics),
            "latency": {
                "avg_ms": sum(latencies) / len(latencies),
                "min_ms": min(latencies),
                "max_ms": max(latencies),
                "p50_ms": sorted(latencies)[len(latencies) // 2],
                "p95_ms": sorted(latencies)[int(len(latencies) * 0.95)],
                "p99_ms": sorted(latencies)[int(len(latencies) * 0.99)]
            },
            "cpu": {
                "avg_percent": sum(cpu_percents) / len(cpu_percents),
                "max_percent": max(cpu_percents)
            },
            "memory": {
                "avg_percent": sum(memory_percents) / len(memory_percents),
                "max_percent": max(memory_percents),
                "current_mb": recent_metrics[-1].memory_mb
            },
            "throughput": {
                "avg_rps": sum(throughputs) / len(throughputs),
                "max_rps": max(throughputs)
            },
            "active_requests": recent_metrics[-1].active_requests
        }

    def get_recent_alerts(
        self,
        limit: int = 10,
        severity: Optional[str] = None
    ) -> List[PerformanceAlert]:
        """获取最近的告警

        Args:
            limit: 返回数量
            severity: 严重程度过滤

        Returns:
            告警列表
        """
        alerts = list(self._alerts)

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        # 按时间倒序
        alerts.sort(key=lambda x: x.timestamp, reverse=True)

        return alerts[:limit]

    def get_optimization_suggestions(self) -> List[str]:
        """获取优化建议

        Returns:
            优化建议列表
        """
        suggestions = []

        if not self._metrics_history:
            return suggestions

        # 分析最近的指标
        recent_metrics = list(self._metrics_history)[-100:]

        # 延迟分析
        avg_latency = sum(m.request_latency_ms for m in recent_metrics) / len(recent_metrics)
        if avg_latency > 500:
            suggestions.append(
                f"Average latency is {avg_latency:.0f}ms. "
                "Consider enabling caching or optimizing slow operations."
            )

        # CPU 分析
        avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
        if avg_cpu > 60:
            suggestions.append(
                f"Average CPU usage is {avg_cpu:.1f}%. "
                "Consider horizontal scaling or optimizing CPU-intensive tasks."
            )

        # 内存分析
        avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
        if avg_memory > 60:
            suggestions.append(
                f"Average memory usage is {avg_memory:.1f}%. "
                "Consider clearing caches or optimizing memory usage."
            )

        # 缓存命中率分析
        cache_hits = sum(m.cache_hit_rate for m in recent_metrics)
        cache_hit_rate = cache_hits / len(recent_metrics)
        if cache_hit_rate < 0.5:
            suggestions.append(
                f"Cache hit rate is {cache_hit_rate:.1%}. "
                "Consider increasing cache size or TTL."
            )

        return suggestions


# 全局实例（单例）
_performance_monitor_instance: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """获取性能监控器实例（单例）

    Returns:
        PerformanceMonitor 实例
    """
    global _performance_monitor_instance

    if _performance_monitor_instance is None:
        _performance_monitor_instance = PerformanceMonitor()
        logger.info("Global PerformanceMonitor instance created")

    return _performance_monitor_instance
