"""
高级 RAG 单元测试
Advanced RAG Unit Tests
"""

import pytest
from unittest.mock import AsyncMock, patch
from app.rag.advanced_rag import SelfRAG, AdaptiveRAG, CRAG


@pytest.mark.unit
@pytest.mark.rag
class TestSelfRAG:
    """Self-RAG 测试"""

    @pytest.fixture
    def self_rag(self):
        """Self-RAG 实例"""
        with patch("app.rag.advanced_rag.HybridRetriever"):
            return SelfRAG(retriever=AsyncMock())

    @pytest.fixture
    def mock_documents(self):
        """Mock 文档"""
        return [
            {"id": "doc1", "text": "相关文档1", "score": 0.9},
            {"id": "doc2", "text": "相关文档2", "score": 0.8}
        ]

    @pytest.mark.asyncio
    async def test_generate_with_retrieval(self, self_rag, mock_documents):
        """测试带检索的生成"""
        # Mock 检索和生成
        self_rag.retriever.hybrid_search = AsyncMock(return_value=mock_documents)
        with patch.object(self_rag, "_generate_answer", return_value="生成的答案"):
            result = await self_rag.generate(
                query="测试查询",
                context={}
            )

            # 验证结果
            assert "answer" in result
            assert "documents" in result
            assert len(result["documents"]) == 2

    @pytest.mark.asyncio
    async def test_relevance_check(self, self_rag, mock_documents):
        """测试相关性检查"""
        # Mock 相关性评分
        with patch.object(self_rag, "_check_relevance", return_value=True):
            is_relevant = await self_rag._check_relevance(
                query="测试查询",
                document=mock_documents[0]
            )

            assert is_relevant is True

    @pytest.mark.asyncio
    async def test_self_critique(self, self_rag):
        """测试自我批评"""
        # Mock 批评
        with patch.object(self_rag, "_critique_answer", return_value={"score": 0.9, "issues": []}):
            critique = await self_rag._critique_answer(
                query="测试查询",
                answer="生成的答案"
            )

            assert "score" in critique
            assert critique["score"] > 0.5


@pytest.mark.unit
@pytest.mark.rag
class TestAdaptiveRAG:
    """Adaptive RAG 测试"""

    @pytest.fixture
    def adaptive_rag(self):
        """Adaptive RAG 实例"""
        with patch("app.rag.advanced_rag.HybridRetriever"):
            return AdaptiveRAG(retriever=AsyncMock())

    @pytest.mark.asyncio
    async def test_adaptive_retrieval(self, adaptive_rag):
        """测试自适应检索"""
        # Mock 检索
        adaptive_rag.retriever.hybrid_search = AsyncMock(return_value=[
            {"id": "doc1", "text": "文档1", "score": 0.9}
        ])

        result = await adaptive_rag.generate(
            query="测试查询",
            context={},
            max_iterations=2
        )

        # 验证迭代检索
        assert "answer" in result
        assert "iterations" in result

    @pytest.mark.asyncio
    async def test_query_refinement(self, adaptive_rag):
        """测试查询优化"""
        original_query = "测试查询"

        # Mock 查询优化
        with patch.object(adaptive_rag, "_refine_query", return_value="优化后的查询"):
            refined = await adaptive_rag._refine_query(
                query=original_query,
                feedback="需要更具体"
            )

            assert refined != original_query

    @pytest.mark.asyncio
    async def test_max_iterations(self, adaptive_rag):
        """测试最大迭代次数"""
        adaptive_rag.retriever.hybrid_search = AsyncMock(return_value=[])

        result = await adaptive_rag.generate(
            query="测试查询",
            context={},
            max_iterations=3
        )

        # 验证不超过最大迭代次数
        assert result.get("iterations", 0) <= 3


@pytest.mark.unit
@pytest.mark.rag
class TestCRAG:
    """CRAG (Corrective RAG) 测试"""

    @pytest.fixture
    def crag(self):
        """CRAG 实例"""
        with patch("app.rag.advanced_rag.HybridRetriever"):
            return CRAG(retriever=AsyncMock())

    @pytest.fixture
    def mock_documents(self):
        """Mock 文档"""
        return [
            {"id": "doc1", "text": "高质量文档", "score": 0.95},
            {"id": "doc2", "text": "低质量文档", "score": 0.3}
        ]

    @pytest.mark.asyncio
    async def test_corrective_retrieval(self, crag, mock_documents):
        """测试纠正性检索"""
        # Mock 检索
        crag.retriever.hybrid_search = AsyncMock(return_value=mock_documents)

        # Mock Web 搜索
        with patch.object(crag, "_web_search", return_value=[
            {"id": "web1", "text": "Web 文档", "score": 0.9}
        ]):
            result = await crag.generate(
                query="测试查询",
                context={},
                max_iterations=2
            )

            # 验证结果
            assert "answer" in result
            assert "documents" in result

    @pytest.mark.asyncio
    async def test_quality_threshold(self, crag, mock_documents):
        """测试质量阈值"""
        # 设置高阈值
        crag.quality_threshold = 0.9

        # Mock 检索（包含低质量文档）
        crag.retriever.hybrid_search = AsyncMock(return_value=mock_documents)

        # Mock Web 搜索
        with patch.object(crag, "_web_search", return_value=[
            {"id": "web1", "text": "高质量 Web 文档", "score": 0.95}
        ]):
            result = await crag.generate(
                query="测试查询",
                context={}
            )

            # 验证触发了 Web 搜索
            assert any(doc["id"].startswith("web") for doc in result.get("documents", []))

    @pytest.mark.asyncio
    async def test_no_web_search_needed(self, crag):
        """测试不需要 Web 搜索的情况"""
        # Mock 高质量检索结果
        high_quality_docs = [
            {"id": "doc1", "text": "高质量文档1", "score": 0.95},
            {"id": "doc2", "text": "高质量文档2", "score": 0.92}
        ]

        crag.retriever.hybrid_search = AsyncMock(return_value=high_quality_docs)

        result = await crag.generate(
            query="测试查询",
            context={}
        )

        # 验证没有 Web 文档
        assert all(not doc["id"].startswith("web") for doc in result.get("documents", []))

    @pytest.mark.asyncio
    async def test_document_filtering(self, crag, mock_documents):
        """测试文档过滤"""
        # Mock 检索（包含低质量文档）
        crag.retriever.hybrid_search = AsyncMock(return_value=mock_documents)

        # 过滤低质量文档
        filtered = await crag._filter_low_quality_documents(
            documents=mock_documents,
            threshold=0.8
        )

        # 验证过滤
        assert len(filtered) < len(mock_documents)
        assert all(doc["score"] >= 0.8 for doc in filtered)
