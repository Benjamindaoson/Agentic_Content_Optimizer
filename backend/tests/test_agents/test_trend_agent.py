"""
TrendAgent 单元测试

测试 TrendAgent 的核心功能：
1. 初始化
2. 执行热点检索
3. GEO 关键词提取
4. 数据库降级检索
5. 参考内容分析
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.content.trend_agent import TrendAgent
from app.agents.base import AgentConfig
from app.models.reference import ViralContent, Platform


class TestTrendAgentInitialization:
    """测试 TrendAgent 初始化"""

    def test_default_initialization(self):
        """测试默认初始化"""
        agent = TrendAgent()

        assert agent.config.name == "TrendAgent"
        assert agent.config.temperature == 0.3
        assert agent.enable_crag is True
        assert agent.use_quality_filter is False

    def test_custom_initialization(self):
        """测试自定义初始化"""
        config = AgentConfig(
            name="CustomTrendAgent",
            description="自定义趋势猎手",
            model="claude-3-5-sonnet-20240620",
            temperature=0.5
        )

        agent = TrendAgent(
            config=config,
            use_quality_filter=True,
            enable_crag=False
        )

        assert agent.config.name == "CustomTrendAgent"
        assert agent.config.temperature == 0.5
        assert agent.enable_crag is False


class TestTrendAgentExecute:
    """测试 TrendAgent 执行"""

    @pytest.mark.asyncio
    async def test_execute_missing_topic(self):
        """测试缺少 topic 参数"""
        agent = TrendAgent()

        input_data = {
            "platform": "xiaohongshu"
        }

        response = await agent.execute(input_data)

        assert response.success is False
        assert "topic" in response.error.lower()

    @pytest.mark.asyncio
    @patch('app.agents.content.trend_agent.TrendAgent._extract_geo_keywords')
    @patch('app.agents.content.trend_agent.EmbeddingService.embed_query')
    @patch('app.agents.content.trend_agent.QdrantRetriever.search')
    async def test_execute_with_vector_results(
        self,
        mock_qdrant_search,
        mock_embed_query,
        mock_extract_geo
    ):
        """测试向量检索成功的情况"""
        # Mock 返回值
        mock_extract_geo.return_value = ["AI", "写作", "工具"]
        mock_embed_query.return_value = [0.1] * 768  # 模拟 embedding
        mock_qdrant_search.return_value = [
            {
                "id": "ref_1",
                "score": 0.9,
                "metadata": {
                    "platform": "xiaohongshu",
                    "text": "AI 写作工具推荐",
                    "engagement_score": 10000,
                    "hook_type": "H01",
                    "body_structure": "B02",
                    "cta_type": "C01"
                }
            }
        ]

        agent = TrendAgent()

        input_data = {
            "topic": "AI 写作工具",
            "platform": "xiaohongshu",
            "limit": 5
        }

        response = await agent.execute(input_data)

        assert response.success is True
        assert "geo_constraints" in response.data
        assert "references" in response.data
        assert len(response.data["references"]) > 0

        # 验证 GEO 关键词
        assert "keywords" in response.data["geo_constraints"]
        assert len(response.data["geo_constraints"]["keywords"]) > 0

    @pytest.mark.asyncio
    @patch('app.agents.content.trend_agent.TrendAgent._extract_geo_keywords')
    @patch('app.agents.content.trend_agent.EmbeddingService.embed_query')
    @patch('app.agents.content.trend_agent.QdrantRetriever.search')
    async def test_execute_with_fallback_to_db(
        self,
        mock_qdrant_search,
        mock_embed_query,
        mock_extract_geo,
        db_session: AsyncSession
    ):
        """测试向量检索失败，降级到数据库检索"""
        # Mock 返回值
        mock_extract_geo.return_value = ["AI", "写作"]
        mock_embed_query.return_value = [0.1] * 768
        mock_qdrant_search.return_value = []  # 向量库为空

        # 创建测试数据
        viral_content = ViralContent(
            platform=Platform.XIAOHONGSHU,
            content_id="test_001",
            author_id="author_001",
            text="这是一个关于 AI 写作的爆款内容",
            engagement_score=10000,
            hook_type="H01",
            body_structure="B02",
            cta_type="C01",
            likes=5000,
            comments=500,
            shares=200,
            collects=300
        )
        db_session.add(viral_content)
        await db_session.commit()

        agent = TrendAgent()

        input_data = {
            "topic": "AI",
            "platform": "xiaohongshu",
            "limit": 5,
            "db": db_session  # 传入数据库会话
        }

        response = await agent.execute(input_data)

        assert response.success is True
        assert "references" in response.data
        # 应该从数据库检索到内容
        assert len(response.data["references"]) > 0


class TestTrendAgentGeoKeywords:
    """测试 GEO 关键词提取"""

    @pytest.mark.asyncio
    @patch('app.agents.content.trend_agent.ClaudeProvider.chat_completion')
    async def test_extract_geo_keywords_success(self, mock_chat):
        """测试成功提取 GEO 关键词"""
        # Mock LLM 响应
        mock_chat.return_value = '{"keywords": ["AI", "写作", "工具", "推荐", "效率"]}'

        agent = TrendAgent()
        keywords = await agent._extract_geo_keywords("AI 写作工具推荐")

        assert len(keywords) == 5
        assert "AI" in keywords
        assert "写作" in keywords

    @pytest.mark.asyncio
    @patch('app.agents.content.trend_agent.ClaudeProvider.chat_completion')
    async def test_extract_geo_keywords_fallback(self, mock_chat):
        """测试 GEO 关键词提取失败，降级处理"""
        # Mock LLM 抛出异常
        mock_chat.side_effect = Exception("LLM error")

        agent = TrendAgent()
        keywords = await agent._extract_geo_keywords("AI 写作工具")

        # 降级：返回原始 topic
        assert len(keywords) == 1
        assert keywords[0] == "AI 写作工具"


class TestTrendAgentFallbackDbSearch:
    """测试数据库降级检索"""

    @pytest.mark.asyncio
    async def test_fallback_db_search_without_session(self):
        """测试没有数据库会话时返回模拟数据"""
        agent = TrendAgent()

        references = await agent._fallback_db_search(
            topic="AI 写作",
            platform="xiaohongshu",
            limit=3,
            db=None  # 没有数据库会话
        )

        # 应该返回模拟数据
        assert len(references) == 3
        assert all("id" in ref for ref in references)
        assert all("score" in ref for ref in references)
        assert all("metadata" in ref for ref in references)

    @pytest.mark.asyncio
    async def test_fallback_db_search_with_session(self, db_session: AsyncSession):
        """测试有数据库会话时查询真实数据"""
        # 创建测试数据
        viral_content = ViralContent(
            platform=Platform.XIAOHONGSHU,
            content_id="test_002",
            author_id="author_002",
            text="AI 写作工具可以大幅提升效率",
            engagement_score=15000,
            hook_type="H02",
            body_structure="B01",
            cta_type="C02",
            likes=8000,
            comments=800,
            shares=300,
            collects=500
        )
        db_session.add(viral_content)
        await db_session.commit()

        agent = TrendAgent()

        references = await agent._fallback_db_search(
            topic="AI",
            platform="xiaohongshu",
            limit=5,
            db=db_session
        )

        # 应该从数据库检索到数据
        assert len(references) > 0
        assert references[0]["id"] == "test_002"
        assert references[0]["metadata"]["text"] == "AI 写作工具可以大幅提升效率"
        assert references[0]["metadata"]["engagement_score"] == 15000

    @pytest.mark.asyncio
    async def test_fallback_db_search_no_results(self, db_session: AsyncSession):
        """测试数据库中没有匹配数据"""
        agent = TrendAgent()

        references = await agent._fallback_db_search(
            topic="不存在的主题",
            platform="xiaohongshu",
            limit=5,
            db=db_session
        )

        # 应该返回空列表
        assert len(references) == 0


class TestTrendAgentAnalyzeReferences:
    """测试参考内容分析"""

    @pytest.mark.asyncio
    async def test_analyze_references(self):
        """测试分析参考内容"""
        agent = TrendAgent()

        references = [
            {
                "id": "ref_1",
                "score": 0.9,
                "metadata": {
                    "platform": "xiaohongshu",
                    "text": "AI 写作工具推荐",
                    "engagement_score": 10000,
                    "hook_type": "H01",
                    "body_structure": "B02",
                    "cta_type": "C01",
                    "image_urls": ["https://example.com/image1.jpg"]
                }
            },
            {
                "id": "ref_2",
                "score": 0.85,
                "metadata": {
                    "platform": "xiaohongshu",
                    "text": "提升写作效率的 AI 工具",
                    "engagement_score": 8000,
                    "hook_type": "H02",
                    "body_structure": "B01",
                    "cta_type": "C02",
                    "image_urls": []
                }
            }
        ]

        analyzed = await agent._analyze_references(references)

        assert len(analyzed) == 2

        # 验证第一个参考内容
        assert analyzed[0]["ref_id"] == "ref_1"
        assert analyzed[0]["similarity_score"] == 0.9
        assert analyzed[0]["text"] == "AI 写作工具推荐"
        assert analyzed[0]["engagement_score"] == 10000
        assert analyzed[0]["structure"]["hook"] == "H01"
        assert analyzed[0]["structure"]["body"] == "B02"
        assert analyzed[0]["structure"]["cta"] == "C01"
        assert len(analyzed[0]["image_urls"]) == 1

        # 验证第二个参考内容
        assert analyzed[1]["ref_id"] == "ref_2"
        assert analyzed[1]["similarity_score"] == 0.85
        assert len(analyzed[1]["image_urls"]) == 0


class TestTrendAgentCRAG:
    """测试 CRAG 补充检索"""

    @pytest.mark.asyncio
    @patch('app.agents.content.trend_agent.TrendAgent._extract_geo_keywords')
    @patch('app.agents.content.trend_agent.EmbeddingService.embed_query')
    @patch('app.agents.content.trend_agent.QdrantRetriever.search')
    @patch('app.agents.content.trend_agent.CorrectiveRAG.generate')
    async def test_execute_with_crag_supplement(
        self,
        mock_crag_generate,
        mock_qdrant_search,
        mock_embed_query,
        mock_extract_geo
    ):
        """测试 CRAG 补充检索"""
        # Mock 返回值
        mock_extract_geo.return_value = ["AI", "写作"]
        mock_embed_query.return_value = [0.1] * 768
        mock_qdrant_search.return_value = [
            {
                "id": "ref_1",
                "score": 0.9,
                "metadata": {
                    "platform": "xiaohongshu",
                    "text": "AI 写作工具",
                    "engagement_score": 10000,
                    "hook_type": "H01",
                    "body_structure": "B02",
                    "cta_type": "C01"
                }
            }
        ]  # 只有 1 个结果，少于 3 个

        # Mock CRAG 返回
        mock_crag_generate.return_value = {
            "iterations": [
                {
                    "documents": [
                        {
                            "id": "crag_1",
                            "score": 0.8,
                            "metadata": {
                                "platform": "xiaohongshu",
                                "text": "CRAG 补充的内容",
                                "engagement_score": 8000
                            }
                        }
                    ]
                }
            ]
        }

        agent = TrendAgent(enable_crag=True)

        input_data = {
            "topic": "AI 写作",
            "platform": "xiaohongshu",
            "limit": 5
        }

        response = await agent.execute(input_data)

        assert response.success is True
        assert len(response.data["references"]) >= 2  # 原始 1 个 + CRAG 补充 1 个

        # 验证 CRAG 被调用
        mock_crag_generate.assert_called_once()
