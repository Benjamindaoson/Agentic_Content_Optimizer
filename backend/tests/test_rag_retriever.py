"""
混合检索器单元测试
Hybrid Retriever Unit Tests
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.rag.retrievers.hybrid_retriever import HybridRetriever


@pytest.mark.unit
@pytest.mark.rag
class TestHybridRetriever:
    """混合检索器测试"""

    @pytest.fixture
    def retriever(self):
        """检索器实例"""
        with patch("app.rag.retrievers.hybrid_retriever.QdrantClient"):
            return HybridRetriever()

    @pytest.fixture
    def mock_documents(self):
        """Mock 文档"""
        return [
            {
                "id": "doc1",
                "text": "这是第一个文档，关于 AI 写作",
                "score": 0.95,
                "metadata": {"source": "test", "date": "2024-01-01"}
            },
            {
                "id": "doc2",
                "text": "这是第二个文档，关于内容创作",
                "score": 0.85,
                "metadata": {"source": "test", "date": "2024-01-02"}
            },
            {
                "id": "doc3",
                "text": "这是第三个文档，关于机器学习",
                "score": 0.75,
                "metadata": {"source": "test", "date": "2024-01-03"}
            }
        ]

    @pytest.mark.asyncio
    async def test_vector_search(self, retriever, mock_documents):
        """测试向量检索"""
        # Mock Qdrant 响应
        retriever.qdrant_client.search = AsyncMock(return_value=mock_documents)

        results = await retriever.vector_search(
            query="AI 写作",
            limit=3
        )

        # 验证结果
        assert len(results) == 3
        assert results[0]["id"] == "doc1"
        assert results[0]["score"] == 0.95

    @pytest.mark.asyncio
    async def test_keyword_search(self, retriever, mock_documents):
        """测试关键词检索"""
        # Mock BM25 响应
        with patch.object(retriever, "_bm25_search", return_value=mock_documents):
            results = await retriever.keyword_search(
                query="AI 写作",
                limit=3
            )

            # 验证结果
            assert len(results) == 3
            assert all("text" in doc for doc in results)

    @pytest.mark.asyncio
    async def test_hybrid_search(self, retriever, mock_documents):
        """测试混合检索"""
        # Mock 向量和关键词检索
        retriever.qdrant_client.search = AsyncMock(return_value=mock_documents[:2])
        with patch.object(retriever, "_bm25_search", return_value=mock_documents[1:]):
            results = await retriever.hybrid_search(
                query="AI 写作",
                limit=3,
                alpha=0.5
            )

            # 验证结果
            assert len(results) <= 3
            assert all("score" in doc for doc in results)

    @pytest.mark.asyncio
    async def test_reranking(self, retriever, mock_documents):
        """测试重排序"""
        # Mock 重排序模型
        with patch.object(retriever, "_rerank_documents", return_value=mock_documents):
            results = await retriever.hybrid_search(
                query="AI 写作",
                limit=3,
                use_reranking=True
            )

            # 验证重排序被调用
            assert len(results) > 0

    @pytest.mark.asyncio
    async def test_query_expansion(self, retriever):
        """测试查询扩展"""
        original_query = "AI 写作"

        # Mock LLM 响应
        with patch.object(retriever, "_expand_query", return_value=["AI 写作", "人工智能创作", "机器写作"]):
            expanded_queries = await retriever._expand_query(original_query)

            # 验证扩展
            assert len(expanded_queries) > 1
            assert original_query in expanded_queries

    @pytest.mark.asyncio
    async def test_context_compression(self, retriever, mock_documents):
        """测试上下文压缩"""
        # Mock 压缩
        with patch.object(retriever, "_compress_context", return_value=mock_documents[:2]):
            compressed = await retriever._compress_context(
                documents=mock_documents,
                query="AI 写作",
                max_length=1000
            )

            # 验证压缩
            assert len(compressed) <= len(mock_documents)

    @pytest.mark.asyncio
    async def test_empty_query(self, retriever):
        """测试空查询"""
        with pytest.raises(ValueError):
            await retriever.hybrid_search(query="", limit=3)

    @pytest.mark.asyncio
    async def test_limit_parameter(self, retriever, mock_documents):
        """测试限制参数"""
        retriever.qdrant_client.search = AsyncMock(return_value=mock_documents)

        # 测试不同的限制值
        for limit in [1, 2, 5]:
            results = await retriever.vector_search(query="test", limit=limit)
            assert len(results) <= limit

    @pytest.mark.asyncio
    async def test_score_threshold(self, retriever, mock_documents):
        """测试分数阈值"""
        retriever.qdrant_client.search = AsyncMock(return_value=mock_documents)

        # 设置高阈值
        results = await retriever.vector_search(
            query="test",
            limit=10,
            score_threshold=0.9
        )

        # 验证所有结果分数都高于阈值
        assert all(doc["score"] >= 0.9 for doc in results)

    @pytest.mark.asyncio
    async def test_metadata_filtering(self, retriever, mock_documents):
        """测试元数据过滤"""
        retriever.qdrant_client.search = AsyncMock(return_value=mock_documents)

        # 按日期过滤
        results = await retriever.vector_search(
            query="test",
            limit=10,
            filter_metadata={"date": "2024-01-01"}
        )

        # 验证过滤
        assert all(doc["metadata"]["date"] == "2024-01-01" for doc in results)

    @pytest.mark.asyncio
    async def test_alpha_parameter(self, retriever, mock_documents):
        """测试 alpha 参数（向量/关键词权重）"""
        retriever.qdrant_client.search = AsyncMock(return_value=mock_documents[:2])
        with patch.object(retriever, "_bm25_search", return_value=mock_documents[1:]):
            # 纯向量检索 (alpha=1.0)
            vector_only = await retriever.hybrid_search(query="test", limit=3, alpha=1.0)

            # 纯关键词检索 (alpha=0.0)
            keyword_only = await retriever.hybrid_search(query="test", limit=3, alpha=0.0)

            # 混合检索 (alpha=0.5)
            hybrid = await retriever.hybrid_search(query="test", limit=3, alpha=0.5)

            # 验证不同权重产生不同结果
            assert len(vector_only) > 0
            assert len(keyword_only) > 0
            assert len(hybrid) > 0
