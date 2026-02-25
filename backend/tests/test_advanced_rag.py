"""
Advanced RAG 单元测试
Tests for Self-RAG, CRAG, Adaptive RAG modes
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.unit
@pytest.mark.rag
class TestAdvancedRAG:
    """Advanced RAG 测试"""

    @pytest.fixture
    def mock_retriever(self):
        """Mock HybridRetriever"""
        retriever = AsyncMock()
        retriever.hybrid_search = AsyncMock(return_value=[
            {"content": "doc1", "score": 0.9},
            {"content": "doc2", "score": 0.8},
        ])
        return retriever

    def test_rag_mode_enum(self):
        """测试 RAG 模式枚举"""
        from app.engine.rag.advanced_rag import RAGMode

        assert RAGMode.STANDARD == "standard"
        assert RAGMode.SELF_RAG == "self_rag"
        assert RAGMode.CRAG == "crag"
        assert RAGMode.ADAPTIVE == "adaptive"
        assert RAGMode.GRAPH == "graph"
        assert RAGMode.MULTI_HOP == "multi_hop"

    @pytest.mark.asyncio
    async def test_self_rag_initialization(self, mock_retriever):
        """测试 SelfRAG 初始化"""
        from app.engine.rag.advanced_rag import SelfRAG

        with patch("app.engine.rag.advanced_rag.UnifiedLLM") as mock_llm:
            rag = SelfRAG(retriever=mock_retriever)
            assert rag.retriever == mock_retriever
            assert rag.llm is not None

    def test_adaptive_rag_initialization(self, mock_retriever):
        """测试 AdaptiveRAG 初始化"""
        from app.engine.rag.advanced_rag import AdaptiveRAG

        with patch("app.engine.rag.advanced_rag.UnifiedLLM"):
            rag = AdaptiveRAG(retriever=mock_retriever)
            assert rag.retriever == mock_retriever
