"""
速率限制器

用于控制爬虫请求频率，避免被封禁
"""

import time
import asyncio
from typing import Dict, Optional
from datetime import datetime, timedelta
from collections import deque
from dataclasses import dataclass, field
import threading


@dataclass
class RateLimitConfig:
    """速率限制配置"""
    max_requests_per_second: float = 2.0  # 每秒最大请求数
    max_requests_per_minute: int = 60  # 每分钟最大请求数
    max_requests_per_hour: int = 1000  # 每小时最大请求数
    burst_size: int = 5  # 突发请求数量
    cooldown_on_error: int = 60  # 错误后冷却时间（秒）


@dataclass
class RequestRecord:
    """请求记录"""
    timestamp: float
    success: bool
    response_time: float = 0.0


class TokenBucket:
    """
    令牌桶算法实现

    用于平滑请求速率，支持突发流量
    """

    def __init__(self, rate: float, capacity: int):
        """
        Args:
            rate: 令牌生成速率（个/秒）
            capacity: 桶容量（最大令牌数）
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self.lock = threading.Lock()

    def consume(self, tokens: int = 1) -> bool:
        """
        消费令牌

        Args:
            tokens: 需要消费的令牌数

        Returns:
            是否成功消费
        """
        with self.lock:
            now = time.time()
            # 补充令牌
            elapsed = now - self.last_update
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.rate
            )
            self.last_update = now

            # 尝试消费
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def wait_time(self, tokens: int = 1) -> float:
        """
        计算需要等待的时间

        Args:
            tokens: 需要的令牌数

        Returns:
            等待时间（秒）
        """
        with self.lock:
            if self.tokens >= tokens:
                return 0.0

            needed = tokens - self.tokens
            return needed / self.rate


class SlidingWindowCounter:
    """
    滑动窗口计数器

    用于统计时间窗口内的请求数
    """

    def __init__(self, window_size: int):
        """
        Args:
            window_size: 窗口大小（秒）
        """
        self.window_size = window_size
        self.requests: deque = deque()
        self.lock = threading.Lock()

    def add_request(self, timestamp: Optional[float] = None):
        """添加请求记录"""
        if timestamp is None:
            timestamp = time.time()

        with self.lock:
            self.requests.append(timestamp)
            self._cleanup()

    def get_count(self) -> int:
        """获取当前窗口内的请求数"""
        with self.lock:
            self._cleanup()
            return len(self.requests)

    def _cleanup(self):
        """清理过期记录"""
        now = time.time()
        cutoff = now - self.window_size

        while self.requests and self.requests[0] < cutoff:
            self.requests.popleft()


class AdaptiveRateLimiter:
    """
    自适应速率限制器

    功能：
    1. 多级速率限制（秒/分钟/小时）
    2. 令牌桶算法支持突发
    3. 错误自动降速
    4. 成功自动提速
    5. 动态调整策略
    """

    def __init__(self, config: RateLimitConfig):
        self.config = config

        # 令牌桶（秒级限制）
        self.token_bucket = TokenBucket(
            rate=config.max_requests_per_second,
            capacity=config.burst_size
        )

        # 滑动窗口（分钟级限制）
        self.minute_window = SlidingWindowCounter(60)

        # 滑动窗口（小时级限制）
        self.hour_window = SlidingWindowCounter(3600)

        # 请求历史
        self.request_history: deque = deque(maxlen=1000)

        # 错误计数
        self.error_count = 0
        self.last_error_time: Optional[float] = None

        # 冷却状态
        self.is_cooling_down = False
        self.cooldown_until: Optional[float] = None

        # 动态速率
        self.current_rate = config.max_requests_per_second
        self.min_rate = config.max_requests_per_second * 0.1
        self.max_rate = config.max_requests_per_second * 1.5

    async def acquire(self) -> bool:
        """
        获取请求许可

        Returns:
            是否获得许可
        """
        # 检查冷却状态
        if self.is_cooling_down:
            if time.time() < self.cooldown_until:
                wait_time = self.cooldown_until - time.time()
                await asyncio.sleep(wait_time)
            else:
                self.is_cooling_down = False
                self.cooldown_until = None

        # 检查小时级限制
        if self.hour_window.get_count() >= self.config.max_requests_per_hour:
            # 等到下一个小时窗口
            await asyncio.sleep(1)
            return await self.acquire()

        # 检查分钟级限制
        if self.minute_window.get_count() >= self.config.max_requests_per_minute:
            # 等到下一个分钟窗口
            await asyncio.sleep(1)
            return await self.acquire()

        # 令牌桶限制
        if not self.token_bucket.consume():
            wait_time = self.token_bucket.wait_time()
            await asyncio.sleep(wait_time)
            return await self.acquire()

        # 记录请求
        now = time.time()
        self.minute_window.add_request(now)
        self.hour_window.add_request(now)

        return True

    def report_success(self, response_time: float):
        """
        报告请求成功

        Args:
            response_time: 响应时间（秒）
        """
        record = RequestRecord(
            timestamp=time.time(),
            success=True,
            response_time=response_time
        )
        self.request_history.append(record)

        # 重置错误计数
        self.error_count = 0

        # 自动提速（如果连续成功）
        if len(self.request_history) >= 10:
            recent = list(self.request_history)[-10:]
            if all(r.success for r in recent):
                self._increase_rate()

    def report_error(self, error_type: str = 'unknown'):
        """
        报告请求失败

        Args:
            error_type: 错误类型
        """
        record = RequestRecord(
            timestamp=time.time(),
            success=False
        )
        self.request_history.append(record)

        self.error_count += 1
        self.last_error_time = time.time()

        # 自动降速
        self._decrease_rate()

        # 严重错误触发冷却
        if error_type in ['rate_limit', 'forbidden', 'banned']:
            self._trigger_cooldown()

    def _increase_rate(self):
        """提高速率"""
        old_rate = self.current_rate
        self.current_rate = min(
            self.max_rate,
            self.current_rate * 1.1
        )

        # 更新令牌桶
        self.token_bucket.rate = self.current_rate

        if self.current_rate != old_rate:
            print(f"Rate increased: {old_rate:.2f} -> {self.current_rate:.2f} req/s")

    def _decrease_rate(self):
        """降低速率"""
        old_rate = self.current_rate
        self.current_rate = max(
            self.min_rate,
            self.current_rate * 0.5
        )

        # 更新令牌桶
        self.token_bucket.rate = self.current_rate

        if self.current_rate != old_rate:
            print(f"Rate decreased: {old_rate:.2f} -> {self.current_rate:.2f} req/s")

    def _trigger_cooldown(self):
        """触发冷却"""
        self.is_cooling_down = True
        self.cooldown_until = time.time() + self.config.cooldown_on_error
        print(f"Cooldown triggered for {self.config.cooldown_on_error}s")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        recent_requests = list(self.request_history)[-100:]

        if not recent_requests:
            return {
                'current_rate': self.current_rate,
                'minute_count': self.minute_window.get_count(),
                'hour_count': self.hour_window.get_count(),
                'success_rate': 0.0,
                'avg_response_time': 0.0,
                'error_count': self.error_count,
                'is_cooling_down': self.is_cooling_down
            }

        success_count = sum(1 for r in recent_requests if r.success)
        success_rate = success_count / len(recent_requests)

        successful_requests = [r for r in recent_requests if r.success]
        avg_response_time = (
            sum(r.response_time for r in successful_requests) / len(successful_requests)
            if successful_requests else 0.0
        )

        return {
            'current_rate': self.current_rate,
            'minute_count': self.minute_window.get_count(),
            'hour_count': self.hour_window.get_count(),
            'success_rate': success_rate,
            'avg_response_time': avg_response_time,
            'error_count': self.error_count,
            'is_cooling_down': self.is_cooling_down,
            'tokens_available': self.token_bucket.tokens
        }


# ==================== 使用示例 ====================

async def example_usage():
    """使用示例"""
    # 创建速率限制器
    config = RateLimitConfig(
        max_requests_per_second=2.0,
        max_requests_per_minute=60,
        max_requests_per_hour=1000,
        burst_size=5,
        cooldown_on_error=60
    )

    limiter = AdaptiveRateLimiter(config)

    # 发起请求
    for i in range(100):
        # 获取许可
        await limiter.acquire()

        # 执行请求
        try:
            # ... 你的请求代码
            start_time = time.time()
            await asyncio.sleep(0.1)  # 模拟请求
            response_time = time.time() - start_time

            # 报告成功
            limiter.report_success(response_time)

        except Exception as e:
            # 报告失败
            limiter.report_error('unknown')

        # 每 10 个请求打印统计
        if (i + 1) % 10 == 0:
            stats = limiter.get_stats()
            print(f"Stats after {i + 1} requests: {stats}")
