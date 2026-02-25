"""
合规缓存层

用于缓存已采集的数据，避免重复请求，降低法律风险
"""

import json
import hashlib
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
import aiofiles
import asyncio
from collections import OrderedDict


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    data: Any
    timestamp: float
    ttl: int  # 生存时间（秒）
    access_count: int = 0
    last_access: float = 0.0

    def is_expired(self) -> bool:
        """是否过期"""
        return time.time() - self.timestamp > self.ttl

    def is_stale(self, stale_threshold: int = 3600) -> bool:
        """是否陈旧（可以刷新但仍可用）"""
        age = time.time() - self.timestamp
        return age > (self.ttl - stale_threshold)


class LRUCache:
    """
    LRU 缓存

    最近最少使用缓存，内存缓存层
    """

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache: OrderedDict = OrderedDict()
        self.lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[CacheEntry]:
        """获取缓存"""
        async with self.lock:
            if key in self.cache:
                entry = self.cache[key]

                # 检查是否过期
                if entry.is_expired():
                    del self.cache[key]
                    return None

                # 更新访问信息
                entry.access_count += 1
                entry.last_access = time.time()

                # 移到末尾（最近使用）
                self.cache.move_to_end(key)

                return entry

            return None

    async def set(self, key: str, entry: CacheEntry):
        """设置缓存"""
        async with self.lock:
            # 如果已存在，先删除
            if key in self.cache:
                del self.cache[key]

            # 添加新条目
            self.cache[key] = entry

            # 如果超过容量，删除最旧的
            if len(self.cache) > self.max_size:
                self.cache.popitem(last=False)

    async def delete(self, key: str):
        """删除缓存"""
        async with self.lock:
            if key in self.cache:
                del self.cache[key]

    async def clear(self):
        """清空缓存"""
        async with self.lock:
            self.cache.clear()

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'usage': len(self.cache) / self.max_size
        }


class DiskCache:
    """
    磁盘缓存

    持久化缓存层，用于长期存储
    """

    def __init__(self, cache_dir: str = './cache'):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.lock = asyncio.Lock()

    def _get_cache_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        # 使用 hash 避免文件名过长
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.json"

    async def get(self, key: str) -> Optional[CacheEntry]:
        """获取缓存"""
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        try:
            async with aiofiles.open(cache_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                data = json.loads(content)

                entry = CacheEntry(
                    key=data['key'],
                    data=data['data'],
                    timestamp=data['timestamp'],
                    ttl=data['ttl'],
                    access_count=data.get('access_count', 0),
                    last_access=data.get('last_access', 0.0)
                )

                # 检查是否过期
                if entry.is_expired():
                    await self.delete(key)
                    return None

                # 更新访问信息
                entry.access_count += 1
                entry.last_access = time.time()

                # 异步更新访问信息（不阻塞）
                asyncio.create_task(self._update_access_info(cache_path, entry))

                return entry

        except Exception as e:
            print(f"Failed to read cache: {e}")
            return None

    async def set(self, key: str, entry: CacheEntry):
        """设置缓存"""
        cache_path = self._get_cache_path(key)

        try:
            data = {
                'key': entry.key,
                'data': entry.data,
                'timestamp': entry.timestamp,
                'ttl': entry.ttl,
                'access_count': entry.access_count,
                'last_access': entry.last_access
            }

            async with aiofiles.open(cache_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, ensure_ascii=False, indent=2))

        except Exception as e:
            print(f"Failed to write cache: {e}")

    async def delete(self, key: str):
        """删除缓存"""
        cache_path = self._get_cache_path(key)

        try:
            if cache_path.exists():
                cache_path.unlink()
        except Exception as e:
            print(f"Failed to delete cache: {e}")

    async def _update_access_info(self, cache_path: Path, entry: CacheEntry):
        """更新访问信息（异步）"""
        try:
            data = {
                'key': entry.key,
                'data': entry.data,
                'timestamp': entry.timestamp,
                'ttl': entry.ttl,
                'access_count': entry.access_count,
                'last_access': entry.last_access
            }

            async with aiofiles.open(cache_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, ensure_ascii=False, indent=2))

        except Exception as e:
            print(f"Failed to update access info: {e}")

    async def cleanup_expired(self):
        """清理过期缓存"""
        count = 0
        for cache_file in self.cache_dir.glob('*.json'):
            try:
                async with aiofiles.open(cache_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    data = json.loads(content)

                    entry = CacheEntry(
                        key=data['key'],
                        data=data['data'],
                        timestamp=data['timestamp'],
                        ttl=data['ttl']
                    )

                    if entry.is_expired():
                        cache_file.unlink()
                        count += 1

            except Exception as e:
                print(f"Failed to check cache file {cache_file}: {e}")

        print(f"Cleaned up {count} expired cache entries")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        cache_files = list(self.cache_dir.glob('*.json'))
        total_size = sum(f.stat().st_size for f in cache_files)

        return {
            'count': len(cache_files),
            'total_size_mb': total_size / (1024 * 1024),
            'cache_dir': str(self.cache_dir)
        }


class ComplianceCache:
    """
    合规缓存管理器

    功能：
    1. 两级缓存（内存 + 磁盘）
    2. 自动过期管理
    3. 陈旧数据刷新
    4. 缓存预热
    5. 统计和监控
    """

    def __init__(
        self,
        memory_size: int = 1000,
        cache_dir: str = './cache',
        default_ttl: int = 86400  # 默认 24 小时
    ):
        self.memory_cache = LRUCache(max_size=memory_size)
        self.disk_cache = DiskCache(cache_dir=cache_dir)
        self.default_ttl = default_ttl

        # 统计信息
        self.hits = 0
        self.misses = 0
        self.stale_hits = 0

    def _make_key(self, prefix: str, identifier: str) -> str:
        """生成缓存键"""
        return f"{prefix}:{identifier}"

    async def get(
        self,
        prefix: str,
        identifier: str,
        allow_stale: bool = True
    ) -> Optional[Dict]:
        """
        获取缓存

        Args:
            prefix: 缓存前缀（如 'note', 'user'）
            identifier: 标识符（如 note_id）
            allow_stale: 是否允许返回陈旧数据

        Returns:
            缓存数据，如果不存在或过期则返回 None
        """
        key = self._make_key(prefix, identifier)

        # 1. 尝试内存缓存
        entry = await self.memory_cache.get(key)

        if entry:
            if not entry.is_stale():
                self.hits += 1
                return entry.data
            elif allow_stale:
                self.stale_hits += 1
                return entry.data

        # 2. 尝试磁盘缓存
        entry = await self.disk_cache.get(key)

        if entry:
            # 回填到内存缓存
            await self.memory_cache.set(key, entry)

            if not entry.is_stale():
                self.hits += 1
                return entry.data
            elif allow_stale:
                self.stale_hits += 1
                return entry.data

        # 3. 缓存未命中
        self.misses += 1
        return None

    async def set(
        self,
        prefix: str,
        identifier: str,
        data: Any,
        ttl: Optional[int] = None
    ):
        """
        设置缓存

        Args:
            prefix: 缓存前缀
            identifier: 标识符
            data: 缓存数据
            ttl: 生存时间（秒），None 则使用默认值
        """
        key = self._make_key(prefix, identifier)

        if ttl is None:
            ttl = self.default_ttl

        entry = CacheEntry(
            key=key,
            data=data,
            timestamp=time.time(),
            ttl=ttl
        )

        # 同时写入内存和磁盘
        await self.memory_cache.set(key, entry)
        await self.disk_cache.set(key, entry)

    async def delete(self, prefix: str, identifier: str):
        """删除缓存"""
        key = self._make_key(prefix, identifier)
        await self.memory_cache.delete(key)
        await self.disk_cache.delete(key)

    async def get_or_fetch(
        self,
        prefix: str,
        identifier: str,
        fetch_func,
        ttl: Optional[int] = None,
        allow_stale: bool = True
    ) -> Optional[Dict]:
        """
        获取缓存或从源获取

        Args:
            prefix: 缓存前缀
            identifier: 标识符
            fetch_func: 获取函数（异步）
            ttl: 生存时间
            allow_stale: 是否允许陈旧数据

        Returns:
            数据
        """
        # 1. 尝试从缓存获取
        cached_data = await self.get(prefix, identifier, allow_stale=allow_stale)

        if cached_data is not None:
            return cached_data

        # 2. 从源获取
        try:
            data = await fetch_func()

            if data is not None:
                # 写入缓存
                await self.set(prefix, identifier, data, ttl)

            return data

        except Exception as e:
            print(f"Failed to fetch data: {e}")
            return None

    async def cleanup(self):
        """清理过期缓存"""
        await self.disk_cache.cleanup_expired()

    async def warmup(self, items: List[tuple]):
        """
        缓存预热

        Args:
            items: [(prefix, identifier, fetch_func, ttl), ...]
        """
        tasks = []
        for prefix, identifier, fetch_func, ttl in items:
            task = self.get_or_fetch(prefix, identifier, fetch_func, ttl, allow_stale=False)
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

    def get_stats(self) -> Dict:
        """获取统计信息"""
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0.0

        return {
            'hits': self.hits,
            'misses': self.misses,
            'stale_hits': self.stale_hits,
            'hit_rate': hit_rate,
            'memory_cache': self.memory_cache.get_stats(),
            'disk_cache': self.disk_cache.get_stats()
        }


# ==================== 使用示例 ====================

async def example_usage():
    """使用示例"""
    # 创建合规缓存
    cache = ComplianceCache(
        memory_size=1000,
        cache_dir='./cache',
        default_ttl=86400  # 24 小时
    )

    # 1. 直接获取/设置
    await cache.set('note', 'abc123', {'title': '测试笔记', 'content': '...'})
    data = await cache.get('note', 'abc123')
    print(f"Cached data: {data}")

    # 2. 获取或从源获取
    async def fetch_note(note_id):
        # 模拟从 API 获取
        await asyncio.sleep(0.1)
        return {'note_id': note_id, 'title': '从 API 获取'}

    data = await cache.get_or_fetch(
        'note',
        'xyz789',
        lambda: fetch_note('xyz789'),
        ttl=3600
    )
    print(f"Fetched data: {data}")

    # 3. 缓存预热
    warmup_items = [
        ('note', 'note1', lambda: fetch_note('note1'), 3600),
        ('note', 'note2', lambda: fetch_note('note2'), 3600),
        ('note', 'note3', lambda: fetch_note('note3'), 3600),
    ]
    await cache.warmup(warmup_items)

    # 4. 获取统计
    stats = cache.get_stats()
    print(f"Cache stats: {stats}")

    # 5. 清理过期缓存
    await cache.cleanup()
