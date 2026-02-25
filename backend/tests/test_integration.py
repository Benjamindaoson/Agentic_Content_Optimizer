"""
集成测试套件
Integration Test Suite

测试完整的工作流程
"""

import pytest
import asyncio
from httpx import AsyncClient
from fastapi.testclient import TestClient

# 导入主应用
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app
from app.core.database import get_db_session


class TestIntegration:
    """集成测试"""

    @pytest.fixture
    def client(self):
        """测试客户端"""
        return TestClient(app)

    def test_health_check(self, client):
        """测试健康检查"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_content_generation_workflow(self, client):
        """测试完整的内容生成工作流"""
        # 1. 生成内容
        response = client.post("/api/generate/content", json={
            "category": "美妆",
            "topic": "冬季护肤",
            "num_candidates": 3,
            "llm_provider": "dots"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["candidates"]) > 0

        # 验证候选内容结构
        candidate = data["candidates"][0]
        assert "title" in candidate
        assert "text" in candidate
        assert "quality_score" in candidate

    def test_pattern_search(self, client):
        """测试模式搜索"""
        response = client.get("/api/patterns/search", params={
            "query": "护肤",
            "category": "美妆",
            "top_k": 5
        })

        assert response.status_code == 200
        data = response.json()
        assert "patterns" in data

    def test_trending_patterns(self, client):
        """测试趋势模式"""
        response = client.get("/api/patterns/trending", params={
            "window_days": 7,
            "top_k": 10
        })

        assert response.status_code == 200
        data = response.json()
        assert "patterns" in data
        assert data["trending_method"] == "time_weighted"

    def test_monitoring_metrics(self, client):
        """测试监控指标"""
        response = client.get("/api/monitoring/metrics", params={
            "time_window_hours": 24
        })

        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        assert "alerts" in data

        # 验证指标结构
        metrics = data["metrics"]
        assert "strategy_entropy" in metrics
        assert "exploration_rate" in metrics
        assert "avg_reward" in metrics

    def test_cover_suggestion(self, client):
        """测试封面建议"""
        response = client.post("/api/generate/cover", json={
            "category": "美妆",
            "topic": "护肤",
            "keywords": ["保湿", "补水", "冬季"],
            "num_suggestions": 3
        })

        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data


class TestRAGSystem:
    """RAG 系统测试"""

    @pytest.mark.asyncio
    async def test_hybrid_retriever(self):
        """测试混合检索器"""
        from app.rag.retrievers.hybrid_retriever import HybridRetriever

        retriever = HybridRetriever()

        # 测试查询扩展
        expanded = await retriever._expand_query("护肤方法", max_expansions=2)
        assert isinstance(expanded, list)

    @pytest.mark.asyncio
    async def test_self_rag(self):
        """测试 Self-RAG"""
        from app.rag.advanced_rag import SelfRAG
        from app.rag.retrievers.hybrid_retriever import HybridRetriever

        retriever = HybridRetriever()
        self_rag = SelfRAG(retriever)

        # 测试生成
        result = await self_rag.generate(
            query="如何护肤",
            context={"platform": "xiaohongshu"},
            max_iterations=1
        )

        assert "answer" in result
        assert "iterations" in result


class TestGrowthBrain:
    """Growth Brain 测试"""

    @pytest.mark.asyncio
    async def test_topic_discovery(self):
        """测试话题发现"""
        from app.growth_brain.auto_account_manager import AutoAccountManager
        from app.core.database import SessionLocal

        db = SessionLocal()
        manager = AutoAccountManager(db)

        # 测试话题发现
        topics = await manager._discover_xhs_trending()

        assert len(topics) > 0
        assert topics[0].topic_name is not None
        assert topics[0].heat_score > 0

        db.close()

    @pytest.mark.asyncio
    async def test_performance_monitoring(self):
        """测试效果监控"""
        from app.growth_brain.auto_account_manager import AutoAccountManager
        from app.core.database import SessionLocal

        db = SessionLocal()
        manager = AutoAccountManager(db)

        # 测试效果监控（使用模拟数据）
        result = await manager.monitor_performance(
            schedule_id="test_schedule_123",
            time_window_minutes=60
        )

        assert "actual_performance" in result
        assert "predicted_performance" in result
        assert "status" in result

        db.close()


class TestLLMIntegration:
    """LLM 集成测试"""

    @pytest.mark.asyncio
    async def test_unified_llm(self):
        """测试统一 LLM"""
        from app.llm.unified import UnifiedLLM

        llm = UnifiedLLM()

        # 测试聊天
        response = await llm.chat(
            messages=[{"role": "user", "content": "你好"}],
            provider="claude",
            model="haiku-4.5",
            max_tokens=50
        )

        assert isinstance(response, str)
        assert len(response) > 0


class TestTracingSystem:
    """追踪系统测试"""

    @pytest.mark.asyncio
    async def test_generation_tracer(self):
        """测试生成追踪器"""
        from app.core.tracer import GenerationTracer

        tracer = GenerationTracer()

        # 开始追踪
        trace_id = tracer.start_trace(
            user_id="test_user",
            input_data={"topic": "测试"}
        )

        assert trace_id is not None

        # 添加阶段
        tracer.trace_trend_retrieval(
            geo_keywords=["测试"],
            references=[{"id": "1", "content": "测试内容"}]
        )

        # 结束追踪
        final_trace_id = await tracer.end_trace(
            output_data={"result": "成功"}
        )

        assert final_trace_id == trace_id


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
