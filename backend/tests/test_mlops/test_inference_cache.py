"""
推理缓存系统单元测试

测试 InferenceCache 的核心功能：
1. 缓存初始化
2. 缓存读写
3. 语义缓存
4. LRU 驱逐
5. 自动过期
6. 缓存统计
"""

import pytest
import time
import numpy as np
from unittest.mock import patch

from app.mlops.inference_cache import InferenceCache, CacheManager


class TestInferenceCacheInitialization:
    """测试缓存初始化"""

    def test_default_initialization(self):
        """测试默认初始化"""
        cache = InferenceCache(
            cache_name="test_cache",
            max_size=100,
            ttl=3600
        )

        assert cache.cache_name == "test_cache"
        assert cache.max_size == 100
        assert cache.ttl == 3600
        assert cache.similarity_threshold == 0.95

    def test_custom_initialization(self):
        """测试自定义初始化"""
        cache = InferenceCache(
            cache_name="custom_cache",
            max_size=200,
            ttl=7200,
            similarity_threshold=0.9
        )

        assert cache.cache_name == "custom_cache"
        assert cache.max_size == 200
        assert cache.ttl == 7200
        assert cache.similarity_threshold == 0.9


class TestInferenceCacheBasicOperations:
    """测试基本缓存操作"""

    def test_set_and_get(self):
        """测试设置和获取缓存"""
        cache = InferenceCache("test", max_size=10, ttl=3600)

        key_data = {"topic": "AI 写作", "platform": "xiaohongshu"}
        value = {"content": "生成的内容"}

        # 设置缓存
        cache.set(key_data, value)

        # 获取缓存
        result = cache.get(key_data)

        assert result is not None
        assert result["content"] == "生成的内容"

    def test_get_nonexistent_key(self):
        """测试获取不存在的键"""
        cache = InferenceCache("test", max_size=10, ttl=3600)

        key_data = {"topic": "不存在的主题"}
        result = cache.get(key_data)

        assert result is None

    def test_overwrite_existing_key(self):
        """测试覆盖现有键"""
        cache = InferenceCache("test", max_size=10, ttl=3600)

        key_data = {"topic": "AI 写作"}

        # 第一次设置
        cache.set(key_data, {"content": "内容1"})

        # 第二次设置（覆盖）
        cache.set(key_data, {"content": "内容2"})

        # 获取缓存
        result = cache.get(key_data)

        assert result["content"] == "内容2"


class TestInferenceCacheSemanticMatching:
    """测试语义缓存"""

    def test_semantic_cache_hit(self):
        """测试语义缓存命中"""
        cache = InferenceCache("test", max_size=10, ttl=3600, similarity_threshold=0.9)

        key_data = {"topic": "AI 写作工具"}
        embedding = np.random.rand(768)  # 模拟 embedding
        value = {"content": "生成的内容"}

        # 设置缓存
        cache.set(key_data, value, embedding=embedding)

        # 使用相似的 embedding 获取缓存
        similar_embedding = embedding + np.random.rand(768) * 0.01  # 非常相似
        result = cache.get({"topic": "AI 写作"}, embedding=similar_embedding)

        # 应该命中语义缓存
        assert result is not None

    def test_semantic_cache_miss(self):
        """测试语义缓存未命中"""
        cache = InferenceCache("test", max_size=10, ttl=3600, similarity_threshold=0.95)

        key_data = {"topic": "AI 写作工具"}
        embedding = np.random.rand(768)
        value = {"content": "生成的内容"}

        # 设置缓存
        cache.set(key_data, value, embedding=embedding)

        # 使用完全不同的 embedding 获取缓存
        different_embedding = np.random.rand(768)
        result = cache.get({"topic": "完全不同的主题"}, embedding=different_embedding)

        # 应该未命中
        assert result is None


class TestInferenceCacheLRU:
    """测试 LRU 驱逐策略"""

    def test_lru_eviction(self):
        """测试 LRU 驱逐"""
        cache = InferenceCache("test", max_size=3, ttl=3600)

        # 添加 3 个缓存项（达到最大容量）
        cache.set({"key": "1"}, {"value": "1"})
        cache.set({"key": "2"}, {"value": "2"})
        cache.set({"key": "3"}, {"value": "3"})

        # 添加第 4 个缓存项（应该驱逐最久未使用的）
        cache.set({"key": "4"}, {"value": "4"})

        # 验证缓存大小
        assert cache.get_stats()["total_entries"] == 3

        # 最早的缓存项应该被驱逐
        assert cache.get({"key": "1"}) is None

    def test_lru_access_updates_order(self):
        """测试访问更新 LRU 顺序"""
        cache = InferenceCache("test", max_size=3, ttl=3600)

        # 添加 3 个缓存项
        cache.set({"key": "1"}, {"value": "1"})
        cache.set({"key": "2"}, {"value": "2"})
        cache.set({"key": "3"}, {"value": "3"})

        # 访问第一个缓存项（更新其访问时间）
        cache.get({"key": "1"})

        # 添加第 4 个缓存项
        cache.set({"key": "4"}, {"value": "4"})

        # 第一个缓存项应该仍然存在（因为最近被访问）
        assert cache.get({"key": "1"}) is not None

        # 第二个缓存项应该被驱逐（最久未访问）
        assert cache.get({"key": "2"}) is None


class TestInferenceCacheTTL:
    """测试自动过期"""

    def test_ttl_expiration(self):
        """测试 TTL 过期"""
        cache = InferenceCache("test", max_size=10, ttl=1)  # 1 秒 TTL

        key_data = {"topic": "AI 写作"}
        value = {"content": "生成的内容"}

        # 设置缓存
        cache.set(key_data, value)

        # 立即获取应该成功
        result = cache.get(key_data)
        assert result is not None

        # 等待 TTL 过期
        time.sleep(1.5)

        # 再次获取应该失败（已过期）
        result = cache.get(key_data)
        assert result is None

    def test_custom_ttl(self):
        """测试自定义 TTL"""
        cache = InferenceCache("test", max_size=10, ttl=3600)

        key_data = {"topic": "AI 写作"}
        value = {"content": "生成的内容"}

        # 设置缓存，使用自定义 TTL（2 秒）
        cache.set(key_data, value, ttl=2)

        # 立即获取应该成功
        result = cache.get(key_data)
        assert result is not None

        # 等待自定义 TTL 过期
        time.sleep(2.5)

        # 再次获取应该失败
        result = cache.get(key_data)
        assert result is None


class TestInferenceCacheStatistics:
    """测试缓存统计"""

    def test_hit_rate_calculation(self):
        """测试命中率计算"""
        cache = InferenceCache("test", max_size=10, ttl=3600)

        key_data = {"topic": "AI 写作"}
        value = {"content": "生成的内容"}

        # 设置缓存
        cache.set(key_data, value)

        # 命中 2 次
        cache.get(key_data)
        cache.get(key_data)

        # 未命中 1 次
        cache.get({"topic": "不存在"})

        # 获取统计
        stats = cache.get_stats()

        assert stats["total_requests"] == 3
        assert stats["cache_hits"] == 2
        assert stats["cache_misses"] == 1
        assert stats["hit_rate"] == pytest.approx(2/3, rel=0.01)

    def test_access_time_tracking(self):
        """测试访问时间追踪"""
        cache = InferenceCache("test", max_size=10, ttl=3600)

        key_data = {"topic": "AI 写作"}
        value = {"content": "生成的内容"}

        # 设置缓存
        cache.set(key_data, value)

        # 获取缓存
        cache.get(key_data)

        # 获取统计
        stats = cache.get_stats()

        assert "avg_access_time_ms" in stats
        assert stats["avg_access_time_ms"] >= 0


class TestInferenceCacheCleanup:
    """测试缓存清理"""

    def test_cleanup_expired_entries(self):
        """测试清理过期条目"""
        cache = InferenceCache("test", max_size=10, ttl=1)

        # 添加多个缓存项
        for i in range(5):
            cache.set({"key": str(i)}, {"value": str(i)})

        # 等待过期
        time.sleep(1.5)

        # 清理过期条目
        removed = cache.cleanup_expired()

        assert removed == 5
        assert cache.get_stats()["total_entries"] == 0

    def test_clear_all(self):
        """测试清空所有缓存"""
        cache = InferenceCache("test", max_size=10, ttl=3600)

        # 添加多个缓存项
        for i in range(5):
            cache.set({"key": str(i)}, {"value": str(i)})

        # 清空缓存
        cache.clear()

        assert cache.get_stats()["total_entries"] == 0


class TestCacheManager:
    """测试缓存管理器"""

    def test_cache_manager_initialization(self):
        """测试缓存管理器初始化"""
        manager = CacheManager()

        assert manager.generation_cache is not None
        assert manager.rag_cache is not None
        assert manager.embedding_cache is not None

    @pytest.mark.asyncio
    async def test_start_cleanup_task(self):
        """测试启动清理任务"""
        manager = CacheManager()

        # 启动清理任务
        await manager.start_cleanup_task(interval=1)

        # 验证任务正在运行
        assert manager._cleanup_task is not None
        assert not manager._cleanup_task.done()

        # 停止清理任务
        await manager.stop_cleanup_task()

    def test_get_overall_stats(self):
        """测试获取整体统计"""
        manager = CacheManager()

        # 添加一些缓存
        manager.generation_cache.set({"key": "1"}, {"value": "1"})
        manager.rag_cache.set({"key": "2"}, {"value": "2"})
        manager.embedding_cache.set({"key": "3"}, {"value": "3"})

        # 获取整体统计
        stats = manager.get_overall_stats()

        assert "generation_cache" in stats
        assert "rag_cache" in stats
        assert "embedding_cache" in stats

        assert stats["generation_cache"]["total_entries"] == 1
        assert stats["rag_cache"]["total_entries"] == 1
        assert stats["embedding_cache"]["total_entries"] == 1


class TestInferenceCacheEdgeCases:
    """测试边界情况"""

    def test_empty_key_data(self):
        """测试空键数据"""
        cache = InferenceCache("test", max_size=10, ttl=3600)

        # 空键数据应该能正常处理
        cache.set({}, {"value": "test"})
        result = cache.get({})

        assert result is not None

    def test_large_value(self):
        """测试大值"""
        cache = InferenceCache("test", max_size=10, ttl=3600)

        # 大值应该能正常存储
        large_value = {"data": "x" * 10000}
        cache.set({"key": "large"}, large_value)

        result = cache.get({"key": "large"})
        assert result is not None
        assert len(result["data"]) == 10000

    def test_concurrent_access(self):
        """测试并发访问"""
        cache = InferenceCache("test", max_size=10, ttl=3600)

        # 模拟并发访问
        for i in range(100):
            cache.set({"key": str(i)}, {"value": str(i)})
            cache.get({"key": str(i)})

        # 应该能正常处理
        stats = cache.get_stats()
        assert stats["total_requests"] == 100
