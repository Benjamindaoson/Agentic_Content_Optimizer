from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.engine.agents.base import BaseAgent, AgentConfig, AgentResponse
from app.engine.rag.retrievers.qdrant_retriever import QdrantRetriever
from app.engine.rag.embeddings.embedding_service import EmbeddingService
from app.engine.rag.advanced_rag import CorrectiveRAG
from app.engine.llm.providers.base import BaseLLMProvider
from app.engine.llm.providers.claude import ClaudeProvider
from app.engine.rag.retrievers.hybrid_retriever import HybridRetriever
from app.models.reference import ViralContent, Platform
import logging

logger = logging.getLogger(__name__)


class TrendAgent(BaseAgent):
    """
    Trend Agent - 趋势猎手

    职责：
    1. 实时检索热点内容
    2. RAG 检索相似爆款
    3. 提取 GEO 关键词
    4. 返回 Reference 元数据

    v4.0 增强：
    - 支持趋势质量过滤（可选）
    - 集成 CRAG 算法补充检索结果
    """

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        llm_provider: Optional[BaseLLMProvider] = None,
        use_quality_filter: bool = False,
        filter_config: Optional[Dict[str, Any]] = None,
        enable_crag: bool = True
    ):
        if config is None:
            config = AgentConfig(
                name="TrendAgent",
                description="热点检索与RAG检索",
                model="claude-3-5-sonnet-20240620",
                temperature=0.3
            )
        super().__init__(config)

        self.qdrant = QdrantRetriever()
        self.embedding = EmbeddingService()
        self.llm: BaseLLMProvider = llm_provider or ClaudeProvider()
        self.hybrid_retriever = HybridRetriever()

        # CRAG 组件（可选）
        self.enable_crag = enable_crag
        if enable_crag:
            self.crag = CorrectiveRAG(self.qdrant)
            logger.info("Trend Agent: CRAG enabled")

        # 趋势质量过滤器（可选）
        self.use_quality_filter = use_quality_filter
        self.quality_filter = None

        if use_quality_filter:
            try:
                from app.engine.rag.trend_quality_filter import TrendQualityFilter, BrandGuidelines

                filter_config = filter_config or {}
                brand_guidelines = BrandGuidelines(filter_config.get('brand_guidelines', {}))

                self.quality_filter = TrendQualityFilter(
                    brand_guidelines=brand_guidelines,
                    weights=filter_config.get('weights', {
                        'freshness': 0.2,
                        'credibility': 0.2,
                        'audience_match': 0.3,
                        'brand_fit': 0.3
                    })
                )
                logger.info("Trend Quality Filter enabled")
            except ImportError:
                logger.warning("Trend Quality Filter not available, using standard retrieval")
                self.use_quality_filter = False

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        执行热点检索

        输入：
        - topic: 话题/产品
        - platform: 平台（xiaohongshu/douyin/tiktok）
        - limit: 返回数量
        - db: 数据库会话（可选）

        输出：
        - geo_constraints: GEO 关键词
        - references: 爆款参考列表
        """
        try:
            topic = input_data.get("topic")
            platform = input_data.get("platform", "xiaohongshu")
            limit = int(input_data.get("limit", 5) or 5)
            rag_hybrid_search = bool(input_data.get("rag_hybrid_search", False))
            rag_query_expansion = bool(input_data.get("rag_query_expansion", True))
            rag_mode = input_data.get("rag_mode", "adaptive")
            db = input_data.get("db")  # 获取数据库会话

            if not topic:
                return AgentResponse(
                    success=False,
                    error="缺少 topic 参数"
                )

            # 1. 提取 GEO 关键词
            geo_keywords = await self._extract_geo_keywords(topic)

            # 2. 检索相似内容（可选：混合检索）
            references = []
            if rag_hybrid_search:
                references = await self.hybrid_retriever.hybrid_search(
                    query=topic,
                    limit=limit,
                    filters={"platform": platform},
                    use_query_expansion=rag_query_expansion,
                    use_reranking=True
                )
            else:
                query_vector = await self.embedding.embed_query(topic)
                references = await self.qdrant.search(
                    query_vector=query_vector,
                    limit=limit,
                    filters={"platform": platform}
                )

            # 3. 如果向量库为空，从数据库检索
            if not references:
                references = await self._fallback_db_search(
                    topic=topic,
                    platform=platform,
                    limit=limit,
                    db=db  # 传入数据库会话
                )

            # 3.5. 如果检索结果仍然不足，使用 CRAG 补充
            # rag_mode=crag 时强制补充
            if (self.enable_crag or rag_mode == "crag") and len(references) < 3:
                logger.info(f"Trend Agent: References insufficient ({len(references)}), using CRAG to supplement")
                crag_result = await self.crag.generate(
                    query=topic,
                    context={"platform": platform, "limit": limit},
                    max_iterations=2
                )

                # 提取 CRAG 检索到的文档
                crag_documents = []
                for iteration in crag_result.get("iterations", []):
                    crag_documents.extend(iteration.get("documents", []))

                # 转换为 references 格式
                for doc in crag_documents[:limit]:
                    references.append({
                        "id": doc.get("id", f"crag_{len(references)}"),
                        "score": doc.get("score", 0.5),
                        "metadata": doc.get("metadata", {})
                    })

                logger.info(f"Trend Agent: After CRAG, total references: {len(references)}")

            # 4. 应用质量过滤（如果启用）
            if self.use_quality_filter and self.quality_filter and references:
                target_audience = input_data.get('target_audience', {})
                filtered_references = self.quality_filter.filter_trends(
                    trends=references,
                    threshold=input_data.get('quality_threshold', 0.6),
                    max_results=limit
                )
                logger.info(
                    f"Quality filter applied: {len(references)} -> {len(filtered_references)} trends"
                )
                references = filtered_references

            # 5. 分析参考内容的结构
            analyzed_references = await self._analyze_references(references)

            response_data = {
                "geo_constraints": {
                    "keywords": geo_keywords,
                    "topic": topic,
                    "platform": platform
                },
                "references": analyzed_references,
                "total_found": len(analyzed_references)
            }

            self._log_execution(input_data, AgentResponse(success=True, data=response_data))

            return AgentResponse(
                success=True,
                data=response_data,
                metadata={
                    "agent": self.config.name,
                    "geo_keywords_count": len(geo_keywords),
                    "references_count": len(analyzed_references)
                }
            )

        except Exception as e:
            return await self._handle_error(e)

    async def _extract_geo_keywords(self, topic: str) -> List[str]:
        """提取 GEO 关键词"""
        try:
            prompt = f"""分析以下话题，提取适合社交媒体搜索的 GEO 关键词。

话题：{topic}

要求：
1. 提取 5-10 个高频搜索关键词
2. 包含核心词、长尾词、相关词
3. 适合 AI 搜索引擎索引
4. 返回 JSON 格式：{{"keywords": ["关键词1", "关键词2", ...]}}

只返回 JSON，不要其他内容。"""

            response = await self.llm.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            )

            # 解析 JSON
            import json
            result = json.loads(response)
            return result.get("keywords", [])

        except Exception as e:
            logger.error(f"Failed to extract GEO keywords: {e}")
            # 降级：简单分词
            return [topic]

    async def _fallback_db_search(
        self,
        topic: str,
        platform: str,
        limit: int,
        db: Optional[AsyncSession] = None
    ) -> List[Dict[str, Any]]:
        """降级：从数据库检索真实爆款内容

        Args:
            topic: 搜索主题
            platform: 平台名称
            limit: 返回数量限制
            db: 数据库会话（可选）

        Returns:
            爆款内容列表
        """
        # 如果没有提供数据库会话，返回模拟数据
        if db is None:
            logger.warning("No database session provided, returning mock data")
            return [
                {
                    "id": f"ref_{i}",
                    "score": 0.9 - i * 0.1,
                    "metadata": {
                        "platform": platform,
                        "text": f"这是关于 {topic} 的爆款内容示例 {i+1}",
                        "engagement_score": 10000 - i * 1000,
                        "hook_type": "H01",
                        "body_structure": "B02",
                        "cta_type": "C01"
                    }
                }
                for i in range(limit)
            ]

        try:
            # 从数据库查询真实爆款内容
            query = (
                select(ViralContent)
                .where(ViralContent.platform == platform)
                .where(ViralContent.text.contains(topic))  # 简单文本匹配
                .order_by(desc(ViralContent.engagement_score))
                .limit(limit)
            )

            result = await db.execute(query)
            viral_contents = result.scalars().all()

            # 如果数据库中没有数据，返回空列表
            if not viral_contents:
                logger.info(f"No viral content found in database for topic: {topic}, platform: {platform}")
                return []

            # 转换为统一格式
            references = []
            for content in viral_contents:
                # 归一化 engagement_score 到 0-1 范围
                normalized_score = min(content.engagement_score / 100000, 1.0)

                references.append({
                    "id": content.content_id,
                    "score": normalized_score,
                    "metadata": {
                        "platform": content.platform.value,
                        "text": content.text,
                        "engagement_score": content.engagement_score,
                        "hook_type": content.hook_type,
                        "body_structure": content.body_structure,
                        "cta_type": content.cta_type,
                        "image_urls": content.image_urls or [],
                        "likes": content.likes,
                        "comments": content.comments,
                        "shares": content.shares,
                        "collects": content.collects,
                        "published_at": content.published_at.isoformat() if content.published_at else None
                    }
                })

            logger.info(f"Found {len(references)} viral contents from database")
            return references

        except Exception as e:
            logger.error(f"Database search failed: {e}", exc_info=True)
            # 降级：返回空列表
            return []

    async def _analyze_references(
        self,
        references: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """分析参考内容的结构"""
        analyzed = []

        for ref in references:
            metadata = ref.get("metadata", {})

            analyzed.append({
                "ref_id": ref.get("id"),
                "similarity_score": ref.get("score", 0),
                "text": metadata.get("text", ""),
                "engagement_score": metadata.get("engagement_score", 0),
                "structure": {
                    "hook": metadata.get("hook_type"),
                    "body": metadata.get("body_structure"),
                    "cta": metadata.get("cta_type")
                },
                "platform": metadata.get("platform"),
                "image_urls": metadata.get("image_urls", [])
            })

        return analyzed
