from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
import logging

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class QdrantRetriever:
    """Qdrant 向量检索器"""

    def __init__(self):
        self.client = QdrantClient(url=settings.QDRANT_URL)
        self.collection_name = settings.QDRANT_COLLECTION
        self.vector_size = settings.QDRANT_VECTOR_SIZE

    async def create_collection(self):
        """创建集合"""
        try:
            collections = self.client.get_collections().collections
            if not any(c.name == self.collection_name for c in collections):
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            raise

    async def upsert_reference(
        self,
        ref_id: str,
        vector: List[float],
        metadata: Dict[str, Any]
    ):
        """插入或更新参考内容"""
        try:
            point = PointStruct(
                id=ref_id,
                vector=vector,
                payload=metadata
            )
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            logger.info(f"Upserted reference: {ref_id}")
        except Exception as e:
            logger.error(f"Failed to upsert reference: {e}")
            raise

    async def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """向量搜索"""
        try:
            # 构建过滤条件
            query_filter = None
            if filters:
                conditions = []
                for key, value in filters.items():
                    conditions.append(
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value)
                        )
                    )
                if conditions:
                    query_filter = Filter(must=conditions)

            # 执行搜索
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                query_filter=query_filter
            )

            # 格式化结果
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "id": result.id,
                    "score": result.score,
                    "metadata": result.payload
                })

            return formatted_results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    async def get_by_id(self, ref_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取参考内容"""
        try:
            result = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[ref_id]
            )
            if result:
                return {
                    "id": result[0].id,
                    "metadata": result[0].payload
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get reference: {e}")
            return None

    async def delete(self, ref_id: str):
        """删除参考内容"""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=[ref_id]
            )
            logger.info(f"Deleted reference: {ref_id}")
        except Exception as e:
            logger.error(f"Failed to delete reference: {e}")
            raise
