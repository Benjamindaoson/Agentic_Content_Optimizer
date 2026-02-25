"""
语义缓存 (Semantic Cache) 核心实现

功能:
1. 将查询文本转为 embedding，在 Qdrant 中检索相似查询的推理结果。
2. 如果余弦相似度 > 阈值，命中缓存直接返回，避免重复调用 LLM。
3. 显著降低长链反思代理 (如 Self-RAG) 的 Token 消耗。
"""

import uuid
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from app.core.config import get_settings
from app.engine.llm.unified import UnifiedLLM

logger = logging.getLogger(__name__)
settings = get_settings()

class SemanticCache:
    """基于 Qdrant 的语义缓存引擎"""

    def __init__(self, collection_name: str = "semantic_cache"):
        self.collection_name = collection_name
        self.client: Optional[QdrantClient] = None
        self.llm = UnifiedLLM() # 用于获取 embeddings
        self.enabled = getattr(settings, "SEMANTIC_CACHE_ENABLED", True)
        self.threshold = getattr(settings, "SEMANTIC_CACHE_SIMILARITY_THRESHOLD", 0.92)
        self.ttl_hours = getattr(settings, "SEMANTIC_CACHE_TTL_HOURS", 24)

    async def _init_client(self):
        """延迟初始化 Qdrant 客户端和集合"""
        if self.client:
            return

        try:
            self.client = QdrantClient(url=settings.QDRANT_URL)
            
            # 检查集合是否存在，不存在则创建
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            
            if not exists:
                logger.info(f"正在创建语义缓存集合: {self.collection_name}")
                # 默认使用 1024 维向量 (符合主流 embedding 模型如 bge-large-zh)
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
                )
        except Exception as e:
            logger.error(f"语义缓存初始化失败: {e}")
            self.enabled = False

    async def get(self, query: str, context: Optional[Dict] = None) -> Optional[str]:
        """查询语义缓存"""
        if not self.enabled:
            return None

        await self._init_client()
        if not self.client: return None

        try:
            # 1. 获取查询向量
            query_vector = await self.llm.get_embedding(query)
            
            # 2. 在 Qdrant 中搜索
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=1,
                with_payload=True,
                score_threshold=self.threshold
            )

            if not search_result:
                return None

            hit = search_result[0]
            payload = hit.payload
            
            # 3. 检查 TTL
            expire_at = payload.get("expire_at")
            if expire_at and datetime.fromisoformat(expire_at) < datetime.now():
                logger.debug(f"缓存已过期: {query[:50]}...")
                self.client.delete(self.collection_name, points_selector=[hit.id])
                return None

            # 4. 辅助校验（可选：上下文匹配）
            if context and payload.get("context_hash"):
                # 这里可以做更复杂的上下文哈希校验，暂略
                pass

            logger.info(f"🚀 [SEMANTIC CACHE HIT] Score: {hit.score:.4f} for query: {query[:50]}...")
            return payload.get("response")

        except Exception as e:
            logger.warning(f"读取语义缓存出错: {e}")
            return None

    async def set(self, query: str, response: str, context: Optional[Dict] = None):
        """写入语义缓存"""
        if not self.enabled:
            return

        await self._init_client()
        if not self.client: return

        try:
            # 1. 获取向量
            vector = await self.llm.get_embedding(query)
            
            # 2. 准备数据
            expire_at = (datetime.now() + timedelta(hours=self.ttl_hours)).isoformat()
            point_id = str(uuid.uuid4())
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={
                            "query": query,
                            "response": response,
                            "created_at": datetime.now().isoformat(),
                            "expire_at": expire_at,
                            "context": context or {}
                        }
                    )
                ]
            )
        except Exception as e:
            logger.warning(f"写入语义缓存出错: {e}")

def semantic_cached(func):
    """语义缓存装饰器 (用于异步函数)"""
    cache = SemanticCache()

    async def wrapper(*args, **kwargs):
        # 简单处理参数，获取第一个字符串作为查询
        query = args[0] if args and isinstance(args[0], str) else kwargs.get("query")
        
        if not query:
            return await func(*args, **kwargs)

        cached_res = await cache.get(query)
        if cached_res:
            return cached_res

        result = await func(*args, **kwargs)
        
        # 只有在结果不为空时才写入缓存
        if result:
            await cache.set(query, result)
            
        return result

    return wrapper
