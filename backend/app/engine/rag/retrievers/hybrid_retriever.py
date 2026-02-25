"""
Hybrid Retriever
混合检索: 向量搜索 + BM25 关键词搜索 + Reranking
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from rank_bm25 import BM25Okapi
import logging

from app.engine.rag.retrievers.qdrant_retriever import QdrantRetriever
from app.engine.rag.embeddings.embedding_service import EmbeddingService
from app.engine.llm.cost_router import get_llm_params

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    混合检索器 (2025 先进 RAG 技术)

    特性:
    1. Hybrid Search: 向量搜索 + BM25 关键词搜索
    2. Reciprocal Rank Fusion (RRF): 融合排序
    3. Query Expansion: 查询扩展
    4. Contextual Compression: 上下文压缩
    """

    def __init__(self):
        self.vector_retriever = QdrantRetriever()
        self.embedding_service = EmbeddingService()

        # BM25 索引：优先 Meilisearch 持久化，降级到内存
        self.bm25_index = None
        self.persistent_bm25 = None
        self.documents = []
        self.doc_ids = []

    async def build_bm25_index(self, documents: List[Dict[str, Any]]):
        """构建 BM25 索引（优先持久化到 Meilisearch）"""
        try:
            self.documents = documents
            self.doc_ids = [doc.get("id") for doc in documents]

            # 尝试使用持久化 BM25
            try:
                from app.engine.rag.retrievers.persistent_bm25 import get_bm25_retriever
                self.persistent_bm25 = await get_bm25_retriever()
                if self.persistent_bm25.available:
                    await self.persistent_bm25.add_documents(documents)
                    logger.info(f"BM25 index persisted to Meilisearch: {len(documents)} docs")
                    return
            except Exception as e:
                logger.debug(f"Meilisearch unavailable, fallback to in-memory: {e}")

            # 降级到内存 BM25
            tokenized_docs = [
                self._tokenize(doc.get("content", ""))
                for doc in documents
            ]
            self.bm25_index = BM25Okapi(tokenized_docs)
            logger.info(f"Built in-memory BM25 index with {len(documents)} documents")

        except Exception as e:
            logger.error(f"Failed to build BM25 index: {e}")
            raise

    async def hybrid_search(
        self,
        query: str,
        limit: int = 10,
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
        filters: Optional[Dict[str, Any]] = None,
        use_query_expansion: bool = True,
        use_reranking: bool = True
    ) -> List[Dict[str, Any]]:
        """
        混合搜索

        Args:
            query: 查询文本
            limit: 返回数量
            vector_weight: 向量搜索权重
            bm25_weight: BM25 权重
            filters: 过滤条件
            use_query_expansion: 是否使用查询扩展
            use_reranking: 是否使用重排序

        Returns:
            排序后的文档列表
        """
        try:
            # 1. 查询扩展 (可选)
            queries = [query]
            if use_query_expansion:
                expanded_queries = await self._expand_query(query)
                queries.extend(expanded_queries)
                logger.info(f"Expanded query: {queries}")

            # 2. 向量搜索
            vector_results = await self._vector_search(
                queries=queries,
                limit=limit * 2,  # 获取更多候选
                filters=filters
            )

            # 3. BM25 搜索
            bm25_results = await self._bm25_search(
                queries=queries,
                limit=limit * 2
            )

            # 4. Reciprocal Rank Fusion (RRF)
            fused_results = self._reciprocal_rank_fusion(
                vector_results=vector_results,
                bm25_results=bm25_results,
                vector_weight=vector_weight,
                bm25_weight=bm25_weight
            )

            # 5. Reranking (可选)
            if use_reranking and len(fused_results) > 0:
                reranked_results = await self._rerank(
                    query=query,
                    documents=fused_results,
                    top_k=limit
                )
                return reranked_results

            return fused_results[:limit]

        except Exception as e:
            logger.error(f"Hybrid search error: {e}")
            raise

    async def _vector_search(
        self,
        queries: List[str],
        limit: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[str, float]]:
        """向量搜索 (支持多查询)"""
        all_results = {}

        for query in queries:
            # 生成查询向量
            query_vector = await self.embedding_service.embed_query(query)

            # 搜索
            results = await self.vector_retriever.search(
                query_vector=query_vector,
                limit=limit,
                filters=filters
            )

            # 合并结果
            for result in results:
                doc_id = result["id"]
                score = result["score"]

                if doc_id not in all_results or score > all_results[doc_id]:
                    all_results[doc_id] = score

        # 排序
        sorted_results = sorted(
            all_results.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return sorted_results

    async def _bm25_search(
        self,
        queries: List[str],
        limit: int
    ) -> List[Tuple[str, float]]:
        """BM25 搜索 (支持多查询，优先 Meilisearch)"""
        # 优先使用持久化 Meilisearch
        if self.persistent_bm25 and self.persistent_bm25.available:
            try:
                all_scores: Dict[str, float] = {}
                for query in queries:
                    results = await self.persistent_bm25.search(query, limit=limit)
                    for r in results:
                        doc_id = r.get("id", "")
                        score = r.get("score", 0.0)
                        if doc_id and (doc_id not in all_scores or score > all_scores[doc_id]):
                            all_scores[doc_id] = score
                sorted_results = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
                return sorted_results[:limit]
            except Exception as e:
                logger.warning(f"Meilisearch BM25 search failed, falling back: {e}")

        if not self.bm25_index:
            logger.warning("BM25 index not built, skipping BM25 search")
            return []

        all_scores = {}

        for query in queries:
            # 分词
            tokenized_query = self._tokenize(query)

            # BM25 评分
            scores = self.bm25_index.get_scores(tokenized_query)

            # 合并结果
            for i, score in enumerate(scores):
                doc_id = self.doc_ids[i]

                if doc_id not in all_scores or score > all_scores[doc_id]:
                    all_scores[doc_id] = score

        # 排序
        sorted_results = sorted(
            all_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return sorted_results[:limit]

    def _reciprocal_rank_fusion(
        self,
        vector_results: List[Tuple[str, float]],
        bm25_results: List[Tuple[str, float]],
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
        k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Reciprocal Rank Fusion (RRF)

        RRF Score = Σ (weight / (k + rank))
        """
        rrf_scores = {}

        # 向量搜索结果
        for rank, (doc_id, score) in enumerate(vector_results, start=1):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + vector_weight / (k + rank)

        # BM25 结果
        for rank, (doc_id, score) in enumerate(bm25_results, start=1):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + bm25_weight / (k + rank)

        # 排序
        sorted_docs = sorted(
            rrf_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # 构建结果
        results = []
        for doc_id, score in sorted_docs:
            # 查找文档内容
            doc = next((d for d in self.documents if d.get("id") == doc_id), None)
            if doc:
                results.append({
                    "id": doc_id,
                    "score": score,
                    "content": doc.get("content"),
                    "metadata": doc.get("metadata", {})
                })

        return results

    async def _expand_query(self, query: str, max_expansions: int = 2) -> List[str]:
        """
        查询扩展（基于 embedding 最近邻 + Redis 缓存）

        用 embedding 相似度在向量库中找到语义相近的已有查询/标题，
        替代 LLM 生成同义查询——零 LLM 成本。
        """
        # 先查 Redis 缓存
        try:
            from app.core.redis import get_redis
            redis = await get_redis()
            import hashlib
            cache_key = f"qe:{hashlib.md5(query.encode()).hexdigest()}"
            cached = await redis.get(cache_key)
            if cached and isinstance(cached, list):
                logger.info(f"Query expansion cache hit: {query[:30]}")
                return cached[:max_expansions]
        except Exception:
            redis = None

        try:
            # 用 embedding 在 Qdrant 中搜索语义相近的已有文档标题
            query_vector = await self.embedding_service.embed_query(query)

            from qdrant_client import QdrantClient
            from app.core.config import get_settings
            settings = get_settings()

            client = QdrantClient(url=settings.QDRANT_URL)
            search_results = client.search(
                collection_name=settings.QDRANT_COLLECTION,
                query_vector=query_vector,
                limit=max_expansions + 3,
                score_threshold=0.6,
            )

            expanded = []
            for hit in search_results:
                title = (hit.payload or {}).get("title", "")
                if title and title != query and len(title) > 2:
                    expanded.append(title)
                if len(expanded) >= max_expansions:
                    break

            # 写入 Redis 缓存（2 小时 TTL）
            if redis and expanded:
                try:
                    await redis.set(cache_key, expanded, expire=7200)
                except Exception:
                    pass

            logger.info(f"Embedding query expansion: {query} -> {expanded}")
            return expanded

        except Exception as e:
            logger.warning(f"Embedding query expansion failed: {e}")
            return []

    async def _rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        重排序 — 优先使用 Cohere Rerank API（成本仅为 LLM 的 1/100），
        降级到基于 embedding 余弦相似度的本地重排序。
        不再使用 LLM 做 Cross-Encoder。
        """
        if not documents:
            return []

        # 策略 1: 尝试 Cohere Rerank（最优质量/成本比）
        try:
            reranked = await self._rerank_cohere(query, documents, top_k)
            if reranked:
                return reranked
        except Exception as e:
            logger.debug(f"Cohere rerank unavailable: {e}")

        # 策略 2: 基于 embedding 余弦相似度重排（零外部调用）
        try:
            return await self._rerank_embedding(query, documents, top_k)
        except Exception as e:
            logger.warning(f"Embedding rerank failed: {e}")

        return documents[:top_k]

    async def _rerank_cohere(
        self, query: str, documents: List[Dict[str, Any]], top_k: int
    ) -> List[Dict[str, Any]]:
        """Cohere Rerank API — 多语言、高精度、低成本"""
        import httpx
        from app.core.config import get_settings
        settings = get_settings()

        api_key = getattr(settings, "COHERE_API_KEY", None)
        if not api_key:
            return []

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.cohere.ai/v1/rerank",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "query": query,
                    "documents": [d.get("content", "")[:1000] for d in documents],
                    "top_n": top_k,
                    "model": "rerank-multilingual-v3.0",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        reranked = []
        for r in data.get("results", []):
            idx = r["index"]
            if 0 <= idx < len(documents):
                doc = documents[idx].copy()
                doc["rerank_score"] = r["relevance_score"]
                reranked.append(doc)

        logger.info(f"Cohere reranked {len(documents)} → top {len(reranked)}")
        return reranked

    async def _rerank_embedding(
        self, query: str, documents: List[Dict[str, Any]], top_k: int
    ) -> List[Dict[str, Any]]:
        """基于 embedding 余弦相似度重排（无外部 API 调用成本）"""
        query_vec = await self.embedding_service.embed_query(query)
        query_arr = np.array(query_vec)

        scored = []
        for doc in documents:
            content = doc.get("content", "")[:500]
            doc_vec = await self.embedding_service.embed_query(content)
            doc_arr = np.array(doc_vec)
            sim = float(np.dot(query_arr, doc_arr) / (
                np.linalg.norm(query_arr) * np.linalg.norm(doc_arr) + 1e-8
            ))
            scored.append((sim, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        result = [doc for _, doc in scored[:top_k]]
        logger.info(f"Embedding reranked {len(documents)} → top {len(result)}")
        return result

    def _tokenize(self, text: str) -> List[str]:
        """简单分词 (中文 + 英文)"""
        import jieba
        return list(jieba.cut(text))

    async def compress_context(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        max_length: int = 2000
    ) -> str:
        """
        上下文压缩

        策略：
        1. 只保留与查询相关的部分
        2. 移除冗余信息
        3. 减少 token 消耗

        Args:
            query: 查询文本
            documents: 文档列表
            max_length: 最大长度（字符）

        Returns:
            压缩后的上下文
        """
        try:
            from app.engine.llm.unified import UnifiedLLM

            llm = UnifiedLLM()

            # 合并文档
            full_context = "\n\n".join([
                doc.get("content", "")
                for doc in documents
            ])

            # 如果已经很短，直接返回
            if len(full_context) <= max_length:
                logger.info(f"Context already short ({len(full_context)} chars), no compression needed")
                return full_context

            # 使用 LLM 压缩
            prompt = f"""给定查询："{query}"

从以下上下文中提取并总结与查询直接相关的信息：

{full_context}

要求：
- 只保留与查询相关的信息
- 移除冗余和无关内容
- 保持信息的准确性
- 控制在 {max_length} 字符以内"""

            compressed = await llm.chat(
                messages=[{"role": "user", "content": prompt}],
                **get_llm_params("trend_extraction"),
            )

            logger.info(f"Context compressed: {len(full_context)} -> {len(compressed)} chars")
            return compressed

        except Exception as e:
            logger.error(f"Context compression error: {e}")
            # 失败时返回截断的原文
            truncated = full_context[:max_length]
            logger.warning(f"Fallback to truncation: {len(truncated)} chars")
            return truncated
