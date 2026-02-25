"""
推理缓存系统

实现智能缓存机制：
1. 语义缓存 - 基于语义相似度的缓存
2. 结果缓存 - 缓存生成结果
3. 向量缓存 - 缓存 embedding 结果
4. 自动过期 - 基于时间和访问频率的过期策略
"""

from typing import Dict, Any, Optional, List, Tuple
import hashlib
import json
import time
from datetime import datetime, timedelta
import logging
import numpy as np
from dataclasses import dataclass
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float
    last_accessed: float
    access_count: int
    ttl: int  # 秒
    metadata: Dict[str, Any]


@dataclass
class CacheStats:
    """缓存统计"""
    total_requests: int
    cache_hits: int
    cache_misses: int
    hit_rate: float
    total_entries: int
    total_size_bytes: int
    avg_access_time_ms: float


class InferenceCache:
    """
    推理缓存系统

    核心功能：
    1. 结果缓存 - 缓存生成的内容
    2. 语义缓存 - 基于相似度匹配
    3. 向量缓存 - 缓存 embedding
    4. 智能过期 - 自动清理过期缓存
    """

    def __init__(
        self,
        max_size: int = 10000,
        default_ttl: int = 3600,  # 1小时
        similarity_threshold: float = 0.95,
        enable_semantic_cache: bool = True
    ):
        """初始化推理缓存

        Args:
            max_size: 最大缓存条目数
            default_ttl: 默认过期时间（秒）
            similarity_threshold: 语义相似度阈值
            enable_semantic_cache: 是否启用语义缓存
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.similarity_threshold = similarity_threshold
        self.enable_semantic_cache = enable_semantic_cache

        # 缓存存储
        self._cache: Dict[str, CacheEntry] = {}

        # 语义缓存（存储 embedding）
        self._semantic_cache: Dict[str, Tuple[np.ndarray, str]] = {}

        # 统计
        self._stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_access_time": 0.0
        }

        logger.info(
            f"InferenceCache initialized: "
            f"max_size={max_size}, ttl={default_ttl}s, "
            f"semantic={enable_semantic_cache}"
        )

    def _generate_key(self, data: Dict[str, Any]) -> str:
        """生成缓存键

        Args:
            data: 数据字典

        Returns:
            缓存键（MD5 哈希）
        """
        # 排序键以确保一致性
        sorted_data = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(sorted_data.encode()).hexdigest()

    def _is_expired(self, entry: CacheEntry) -> bool:
        """检查缓存是否过期

        Args:
            entry: 缓存条目

        Returns:
            是否过期
        """
        current_time = time.time()
        age = current_time - entry.created_at
        return age > entry.ttl

    def _evict_if_needed(self):
        """如果需要，驱逐缓存条目"""
        if len(self._cache) < self.max_size:
            return

        # 驱逐策略：LRU（最近最少使用）
        # 按最后访问时间排序
        sorted_entries = sorted(
            self._cache.items(),
            key=lambda x: x[1].last_accessed
        )

        # 删除最旧的 10%
        num_to_evict = max(1, len(self._cache) // 10)
        for i in range(num_to_evict):
            key = sorted_entries[i][0]
            del self._cache[key]

            # 同时删除语义缓存
            if key in self._semantic_cache:
                del self._semantic_cache[key]

        logger.info(f"Evicted {num_to_evict} cache entries")

    def get(
        self,
        key_data: Dict[str, Any],
        embedding: Optional[np.ndarray] = None
    ) -> Optional[Any]:
        """获取缓存值

        Args:
            key_data: 键数据
            embedding: 查询的 embedding（用于语义缓存）

        Returns:
            缓存值，如果不存在返回 None
        """
        start_time = time.time()
        self._stats["total_requests"] += 1

        # 1. 精确匹配
        key = self._generate_key(key_data)

        if key in self._cache:
            entry = self._cache[key]

            # 检查是否过期
            if self._is_expired(entry):
                del self._cache[key]
                if key in self._semantic_cache:
                    del self._semantic_cache[key]
                self._stats["cache_misses"] += 1
                return None

            # 更新访问信息
            entry.last_accessed = time.time()
            entry.access_count += 1

            self._stats["cache_hits"] += 1
            access_time = (time.time() - start_time) * 1000
            self._stats["total_access_time"] += access_time

            logger.debug(f"Cache hit: {key[:8]}, access_time={access_time:.2f}ms")
            return entry.value

        # 2. 语义匹配（如果启用且提供了 embedding）
        if self.enable_semantic_cache and embedding is not None:
            best_similarity = 0.0
            best_key = None

            for cached_key, (cached_embedding, _) in self._semantic_cache.items():
                # 计算余弦相似度
                similarity = np.dot(embedding, cached_embedding) / (
                    np.linalg.norm(embedding) * np.linalg.norm(cached_embedding)
                )

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_key = cached_key

            # 如果相似度超过阈值，返回缓存结果
            if best_similarity >= self.similarity_threshold and best_key in self._cache:
                entry = self._cache[best_key]

                if not self._is_expired(entry):
                    entry.last_accessed = time.time()
                    entry.access_count += 1

                    self._stats["cache_hits"] += 1
                    access_time = (time.time() - start_time) * 1000
                    self._stats["total_access_time"] += access_time

                    logger.debug(
                        f"Semantic cache hit: {best_key[:8]}, "
                        f"similarity={best_similarity:.4f}, "
                        f"access_time={access_time:.2f}ms"
                    )
                    return entry.value

        # 缓存未命中
        self._stats["cache_misses"] += 1
        return None

    def set(
        self,
        key_data: Dict[str, Any],
        value: Any,
        ttl: Optional[int] = None,
        embedding: Optional[np.ndarray] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """设置缓存值

        Args:
            key_data: 键数据
            value: 缓存值
            ttl: 过期时间（秒），None 使用默认值
            embedding: 查询的 embedding（用于语义缓存）
            metadata: 元数据
        """
        # 驱逐检查
        self._evict_if_needed()

        key = self._generate_key(key_data)
        current_time = time.time()

        # 创建缓存条目
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=current_time,
            last_accessed=current_time,
            access_count=0,
            ttl=ttl or self.default_ttl,
            metadata=metadata or {}
        )

        self._cache[key] = entry

        # 存储语义缓存
        if self.enable_semantic_cache and embedding is not None:
            self._semantic_cache[key] = (embedding, key)

        logger.debug(f"Cache set: {key[:8]}, ttl={entry.ttl}s")

    def delete(self, key_data: Dict[str, Any]):
        """删除缓存

        Args:
            key_data: 键数据
        """
        key = self._generate_key(key_data)

        if key in self._cache:
            del self._cache[key]

        if key in self._semantic_cache:
            del self._semantic_cache[key]

        logger.debug(f"Cache deleted: {key[:8]}")

    def clear(self):
        """清空所有缓存"""
        self._cache.clear()
        self._semantic_cache.clear()
        logger.info("Cache cleared")

    def cleanup_expired(self) -> int:
        """清理过期缓存

        Returns:
            清理的条目数
        """
        expired_keys = []

        for key, entry in self._cache.items():
            if self._is_expired(entry):
                expired_keys.append(key)

        for key in expired_keys:
            del self._cache[key]
            if key in self._semantic_cache:
                del self._semantic_cache[key]

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired entries")

        return len(expired_keys)

    def get_stats(self) -> CacheStats:
        """获取缓存统计

        Returns:
            缓存统计
        """
        total_requests = self._stats["total_requests"]
        cache_hits = self._stats["cache_hits"]
        cache_misses = self._stats["cache_misses"]

        hit_rate = cache_hits / total_requests if total_requests > 0 else 0.0

        avg_access_time = (
            self._stats["total_access_time"] / cache_hits
            if cache_hits > 0 else 0.0
        )

        # 估算缓存大小
        total_size = sum(
            len(json.dumps(entry.value, ensure_ascii=False).encode())
            for entry in self._cache.values()
        )

        return CacheStats(
            total_requests=total_requests,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            hit_rate=hit_rate,
            total_entries=len(self._cache),
            total_size_bytes=total_size,
            avg_access_time_ms=avg_access_time
        )

    def get_top_entries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取访问最多的缓存条目

        Args:
            limit: 返回数量

        Returns:
            Top 条目列表
        """
        sorted_entries = sorted(
            self._cache.values(),
            key=lambda x: x.access_count,
            reverse=True
        )

        return [
            {
                "key": entry.key[:8],
                "access_count": entry.access_count,
                "age_seconds": time.time() - entry.created_at,
                "ttl": entry.ttl,
                "metadata": entry.metadata
            }
            for entry in sorted_entries[:limit]
        ]


class CacheManager:
    """
    缓存管理器

    管理多个缓存实例：
    1. 生成结果缓存
    2. RAG 检索缓存
    3. Embedding 缓存
    """

    def __init__(self):
        """初始化缓存管理器"""
        # 生成结果缓存（较长 TTL）
        self.generation_cache = InferenceCache(
            max_size=1000,
            default_ttl=7200,  # 2小时
            enable_semantic_cache=True
        )

        # RAG 检索缓存（中等 TTL）
        self.rag_cache = InferenceCache(
            max_size=5000,
            default_ttl=3600,  # 1小时
            enable_semantic_cache=True
        )

        # Embedding 缓存（较长 TTL）
        self.embedding_cache = InferenceCache(
            max_size=10000,
            default_ttl=86400,  # 24小时
            enable_semantic_cache=False  # embedding 本身不需要语义缓存
        )

        # 启动后台清理任务
        self._cleanup_task = None

        logger.info("CacheManager initialized")

    async def start_cleanup_task(self, interval: int = 300):
        """启动后台清理任务

        Args:
            interval: 清理间隔（秒）
        """
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(interval)

                    # 清理所有缓存
                    total_cleaned = 0
                    total_cleaned += self.generation_cache.cleanup_expired()
                    total_cleaned += self.rag_cache.cleanup_expired()
                    total_cleaned += self.embedding_cache.cleanup_expired()

                    if total_cleaned > 0:
                        logger.info(f"Background cleanup: removed {total_cleaned} entries")

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Cleanup task error: {e}", exc_info=True)

        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info(f"Started background cleanup task (interval={interval}s)")

    async def stop_cleanup_task(self):
        """停止后台清理任务"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped background cleanup task")

    def get_overall_stats(self) -> Dict[str, Any]:
        """获取所有缓存的统计

        Returns:
            统计信息
        """
        gen_stats = self.generation_cache.get_stats()
        rag_stats = self.rag_cache.get_stats()
        emb_stats = self.embedding_cache.get_stats()

        return {
            "generation_cache": {
                "hit_rate": gen_stats.hit_rate,
                "total_entries": gen_stats.total_entries,
                "total_requests": gen_stats.total_requests,
                "avg_access_time_ms": gen_stats.avg_access_time_ms
            },
            "rag_cache": {
                "hit_rate": rag_stats.hit_rate,
                "total_entries": rag_stats.total_entries,
                "total_requests": rag_stats.total_requests,
                "avg_access_time_ms": rag_stats.avg_access_time_ms
            },
            "embedding_cache": {
                "hit_rate": emb_stats.hit_rate,
                "total_entries": emb_stats.total_entries,
                "total_requests": emb_stats.total_requests,
                "avg_access_time_ms": emb_stats.avg_access_time_ms
            },
            "total_size_bytes": (
                gen_stats.total_size_bytes +
                rag_stats.total_size_bytes +
                emb_stats.total_size_bytes
            )
        }


# 全局实例（单例）
_cache_manager_instance: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """获取缓存管理器实例（单例）

    Returns:
        CacheManager 实例
    """
    global _cache_manager_instance

    if _cache_manager_instance is None:
        _cache_manager_instance = CacheManager()
        logger.info("Global CacheManager instance created")

    return _cache_manager_instance
