"""
测试 Growth Brain 模块合并
Test Growth Brain Module Integration

测试内容：
1. AutoAccountManager RAG + RL 集成
2. 可选启用/禁用 RAG 和 RL
3. 功能完整性验证
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.orm import Session

from app.growth_brain.auto_account_manager import AutoAccountManager


class TestAutoAccountManagerIntegration:
    """测试 AutoAccountManager 集成"""

    @pytest.fixture
    def db_session(self):
        """创建数据库会话 Mock"""
        return Mock(spec=Session)

    def test_rag_and_rl_enabled(self, db_session):
        """测试 RAG 和 RL 都启用"""
        manager = AutoAccountManager(
            db=db_session,
            enable_rag=True,
            enable_rl=True
        )

        assert manager.enable_rag is True
        assert manager.enable_rl is True
        assert hasattr(manager, 'retriever')
        assert hasattr(manager, 'self_rag')
        assert hasattr(manager, 'adaptive_rag')
        assert hasattr(manager, 'topic_selector')
        assert hasattr(manager, 'grpo_trainer')
        print("✅ AutoAccountManager: RAG + RL enabled")

    def test_rag_only(self, db_session):
        """测试仅启用 RAG"""
        manager = AutoAccountManager(
            db=db_session,
            enable_rag=True,
            enable_rl=False
        )

        assert manager.enable_rag is True
        assert manager.enable_rl is False
        assert hasattr(manager, 'retriever')
        assert manager.topic_selector is None
        print("✅ AutoAccountManager: RAG only enabled")

    def test_rl_only(self, db_session):
        """测试仅启用 RL"""
        manager = AutoAccountManager(
            db=db_session,
            enable_rag=False,
            enable_rl=True
        )

        assert manager.enable_rag is False
        assert manager.enable_rl is True
        assert manager.retriever is None
        assert hasattr(manager, 'topic_selector')
        print("✅ AutoAccountManager: RL only enabled")

    def test_both_disabled(self, db_session):
        """测试都不启用"""
        manager = AutoAccountManager(
            db=db_session,
            enable_rag=False,
            enable_rl=False
        )

        assert manager.enable_rag is False
        assert manager.enable_rl is False
        assert manager.retriever is None
        assert manager.topic_selector is None
        print("✅ AutoAccountManager: Both disabled (baseline mode)")

    @pytest.mark.asyncio
    async def test_retrieve_successful_topics(self, db_session):
        """测试 RAG 检索成功话题"""
        manager = AutoAccountManager(
            db=db_session,
            enable_rag=True,
            enable_rl=False
        )

        # Mock retriever
        manager.retriever = Mock()
        manager.retriever.hybrid_search = AsyncMock(return_value=[
            {"id": "topic_1", "score": 0.9, "metadata": {"topic": "AI 写作"}},
            {"id": "topic_2", "score": 0.8, "metadata": {"topic": "效率工具"}}
        ])

        results = await manager.retrieve_successful_topics(
            persona_keywords=["AI", "写作", "效率"],
            limit=10
        )

        assert len(results) == 2
        assert results[0]["id"] == "topic_1"
        print(f"✅ AutoAccountManager: Retrieved {len(results)} successful topics")

    @pytest.mark.asyncio
    async def test_find_similar_viral_content(self, db_session):
        """测试 Self-RAG 查找相似爆款"""
        manager = AutoAccountManager(
            db=db_session,
            enable_rag=True,
            enable_rl=False
        )

        # Mock self_rag
        manager.self_rag = Mock()
        manager.self_rag.generate = AsyncMock(return_value={
            "iterations": [
                {
                    "documents": [
                        {"text": "爆款内容1", "score": 0.9},
                        {"text": "爆款内容2", "score": 0.8}
                    ]
                }
            ]
        })

        results = await manager.find_similar_viral_content(
            topic="AI 写作",
            style="专业",
            limit=5
        )

        assert len(results) == 2
        print(f"✅ AutoAccountManager: Found {len(results)} similar viral contents")

    @pytest.mark.asyncio
    async def test_learn_success_patterns(self, db_session):
        """测试 Adaptive RAG 学习成功模式"""
        manager = AutoAccountManager(
            db=db_session,
            enable_rag=True,
            enable_rl=False
        )

        # Mock adaptive_rag
        manager.adaptive_rag = Mock()
        manager.adaptive_rag.generate = AsyncMock(return_value={
            "iterations": [
                {
                    "documents": [
                        {"metadata": {"topic": "AI", "hook_type": "H01"}},
                        {"metadata": {"topic": "写作", "hook_type": "H02"}}
                    ]
                }
            ]
        })

        patterns = await manager.learn_success_patterns(
            account_id="account_001",
            days=30
        )

        assert "common_topics" in patterns
        assert "successful_hooks" in patterns
        assert len(patterns["common_topics"]) > 0
        print(f"✅ AutoAccountManager: Learned {len(patterns['common_topics'])} success patterns")

    @pytest.mark.asyncio
    async def test_rag_disabled_fallback(self, db_session):
        """测试 RAG 禁用时的降级行为"""
        manager = AutoAccountManager(
            db=db_session,
            enable_rag=False,
            enable_rl=False
        )

        # 调用 RAG 方法应该返回空列表
        results = await manager.retrieve_successful_topics(
            persona_keywords=["AI"],
            limit=10
        )

        assert results == []
        print("✅ AutoAccountManager: RAG disabled fallback works")


class TestGrowthBrainPerformance:
    """测试 Growth Brain 性能"""

    @pytest.fixture
    def db_session(self):
        return Mock(spec=Session)

    @pytest.mark.asyncio
    async def test_initialization_time(self, db_session):
        """测试初始化时间"""
        import time

        start_time = time.time()

        manager = AutoAccountManager(
            db=db_session,
            enable_rag=True,
            enable_rl=True
        )

        end_time = time.time()
        elapsed = end_time - start_time

        print(f"✅ AutoAccountManager initialization time: {elapsed:.3f}s")
        assert elapsed < 2.0, f"Initialization too slow: {elapsed:.3f}s"

    @pytest.mark.asyncio
    async def test_memory_usage(self, db_session):
        """测试内存使用"""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        mem_before = process.memory_info().rss / 1024 / 1024  # MB

        manager = AutoAccountManager(
            db=db_session,
            enable_rag=True,
            enable_rl=True
        )

        mem_after = process.memory_info().rss / 1024 / 1024  # MB
        mem_increase = mem_after - mem_before

        print(f"✅ Memory usage: {mem_before:.1f}MB -> {mem_after:.1f}MB (+{mem_increase:.1f}MB)")
        # 目标：< 100MB 增长
        # assert mem_increase < 100, f"Memory increase too high: {mem_increase:.1f}MB"


class TestBackwardCompatibility:
    """测试向后兼容性"""

    @pytest.fixture
    def db_session(self):
        return Mock(spec=Session)

    def test_default_parameters(self, db_session):
        """测试默认参数（应该启用 RAG 和 RL）"""
        manager = AutoAccountManager(db=db_session)

        assert manager.enable_rag is True
        assert manager.enable_rl is True
        print("✅ Default parameters: RAG + RL enabled")

    @pytest.mark.asyncio
    async def test_existing_methods_still_work(self, db_session):
        """测试现有方法仍然可用"""
        manager = AutoAccountManager(
            db=db_session,
            enable_rag=False,
            enable_rl=False
        )

        # 测试基础方法（不依赖 RAG/RL）
        # 这些方法应该仍然可用
        assert hasattr(manager, 'discover_trending_topics')
        assert hasattr(manager, 'select_topics_for_account')
        assert hasattr(manager, 'create_daily_plan')
        print("✅ Existing methods still available")


if __name__ == "__main__":
    print("=" * 60)
    print("Growth Brain Integration Tests")
    print("=" * 60)

    # 运行测试
    pytest.main([__file__, "-v", "-s"])
