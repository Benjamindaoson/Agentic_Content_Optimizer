"""
代理池管理器

用于爬虫的 IP 代理轮换，降低被封风险
"""

from typing import List, Dict, Optional
import random
import time
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio
import aiohttp


@dataclass
class Proxy:
    """代理信息"""
    ip: str
    port: int
    protocol: str  # http/https/socks5
    username: Optional[str] = None
    password: Optional[str] = None

    # 状态信息
    success_count: int = 0
    fail_count: int = 0
    last_used: Optional[datetime] = None
    last_check: Optional[datetime] = None
    is_available: bool = True
    response_time: float = 0.0  # 响应时间（秒）

    @property
    def url(self) -> str:
        """代理 URL"""
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.ip}:{self.port}"
        return f"{self.protocol}://{self.ip}:{self.port}"

    @property
    def success_rate(self) -> float:
        """成功率"""
        total = self.success_count + self.fail_count
        return self.success_count / total if total > 0 else 0.0


class ProxyPool:
    """
    代理池管理器

    功能：
    1. 代理轮换
    2. 健康检查
    3. 自动剔除失效代理
    4. 智能选择（基于成功率和响应时间）
    """

    def __init__(
        self,
        check_interval: int = 300,  # 健康检查间隔（秒）
        max_fail_count: int = 5,  # 最大失败次数
        timeout: int = 10  # 超时时间（秒）
    ):
        self.proxies: List[Proxy] = []
        self.check_interval = check_interval
        self.max_fail_count = max_fail_count
        self.timeout = timeout
        self._check_task = None

    def add_proxy(
        self,
        ip: str,
        port: int,
        protocol: str = 'http',
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """添加代理"""
        proxy = Proxy(
            ip=ip,
            port=port,
            protocol=protocol,
            username=username,
            password=password
        )
        self.proxies.append(proxy)

    def add_proxies_from_list(self, proxy_list: List[Dict]):
        """批量添加代理"""
        for proxy_info in proxy_list:
            self.add_proxy(**proxy_info)

    def get_proxy(self, strategy: str = 'smart') -> Optional[Proxy]:
        """
        获取代理

        Args:
            strategy: 选择策略
                - random: 随机选择
                - round_robin: 轮询
                - smart: 智能选择（基于成功率和响应时间）

        Returns:
            代理对象
        """
        available_proxies = [p for p in self.proxies if p.is_available]

        if not available_proxies:
            return None

        if strategy == 'random':
            proxy = random.choice(available_proxies)

        elif strategy == 'round_robin':
            # 选择最久未使用的
            proxy = min(
                available_proxies,
                key=lambda p: p.last_used or datetime.min
            )

        elif strategy == 'smart':
            # 智能选择：综合考虑成功率和响应时间
            def score(p: Proxy) -> float:
                # 成功率权重 0.7，响应时间权重 0.3
                success_score = p.success_rate
                # 响应时间越短越好，归一化到 0-1
                time_score = max(0, 1 - p.response_time / 10)
                return 0.7 * success_score + 0.3 * time_score

            proxy = max(available_proxies, key=score)

        else:
            proxy = random.choice(available_proxies)

        proxy.last_used = datetime.now()
        return proxy

    def mark_success(self, proxy: Proxy, response_time: float):
        """标记代理成功"""
        proxy.success_count += 1
        proxy.response_time = response_time
        proxy.is_available = True

    def mark_failure(self, proxy: Proxy):
        """标记代理失败"""
        proxy.fail_count += 1

        # 失败次数过多，标记为不可用
        if proxy.fail_count >= self.max_fail_count:
            proxy.is_available = False

    async def check_proxy(self, proxy: Proxy, test_url: str = 'https://www.baidu.com') -> bool:
        """
        检查代理是否可用

        Args:
            proxy: 代理对象
            test_url: 测试 URL

        Returns:
            是否可用
        """
        try:
            start_time = time.time()

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    test_url,
                    proxy=proxy.url,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        response_time = time.time() - start_time
                        self.mark_success(proxy, response_time)
                        proxy.last_check = datetime.now()
                        return True

        except Exception as e:
            self.mark_failure(proxy)
            proxy.last_check = datetime.now()
            return False

        return False

    async def check_all_proxies(self, test_url: str = 'https://www.baidu.com'):
        """检查所有代理"""
        tasks = [self.check_proxy(proxy, test_url) for proxy in self.proxies]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def start_health_check(self, test_url: str = 'https://www.baidu.com'):
        """启动健康检查任务"""
        while True:
            await self.check_all_proxies(test_url)
            await asyncio.sleep(self.check_interval)

    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = len(self.proxies)
        available = sum(1 for p in self.proxies if p.is_available)

        if total == 0:
            return {
                'total': 0,
                'available': 0,
                'unavailable': 0,
                'avg_success_rate': 0.0,
                'avg_response_time': 0.0
            }

        avg_success_rate = sum(p.success_rate for p in self.proxies) / total
        avg_response_time = sum(p.response_time for p in self.proxies if p.response_time > 0) / max(1, sum(1 for p in self.proxies if p.response_time > 0))

        return {
            'total': total,
            'available': available,
            'unavailable': total - available,
            'avg_success_rate': avg_success_rate,
            'avg_response_time': avg_response_time
        }

    def remove_unavailable(self):
        """移除不可用的代理"""
        self.proxies = [p for p in self.proxies if p.is_available]


# ==================== 代理提供商集成 ====================

class ProxyProvider:
    """代理提供商基类"""

    async def fetch_proxies(self) -> List[Dict]:
        """获取代理列表"""
        raise NotImplementedError


class KuaidailiProvider(ProxyProvider):
    """快代理"""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def fetch_proxies(self) -> List[Dict]:
        """从快代理获取代理"""
        # TODO: 实现快代理 API 调用
        return []


class ZhimaProvider(ProxyProvider):
    """芝麻代理"""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def fetch_proxies(self) -> List[Dict]:
        """从芝麻代理获取代理"""
        # TODO: 实现芝麻代理 API 调用
        return []


# ==================== 使用示例 ====================

async def example_usage():
    """使用示例"""
    # 创建代理池
    pool = ProxyPool(
        check_interval=300,
        max_fail_count=5,
        timeout=10
    )

    # 添加代理
    pool.add_proxy('127.0.0.1', 7890, 'http')
    pool.add_proxy('127.0.0.1', 7891, 'http')

    # 或批量添加
    proxy_list = [
        {'ip': '127.0.0.1', 'port': 7890, 'protocol': 'http'},
        {'ip': '127.0.0.1', 'port': 7891, 'protocol': 'http'},
    ]
    pool.add_proxies_from_list(proxy_list)

    # 启动健康检查（后台任务）
    asyncio.create_task(pool.start_health_check())

    # 获取代理
    proxy = pool.get_proxy(strategy='smart')
    if proxy:
        print(f"使用代理: {proxy.url}")

        # 使用代理进行请求
        try:
            # ... 你的请求代码
            pool.mark_success(proxy, 0.5)
        except:
            pool.mark_failure(proxy)

    # 获取统计信息
    stats = pool.get_stats()
    print(f"代理池统计: {stats}")
