from typing import List, Union
import httpx
import logging
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class EmbeddingService:
    """Embedding 服务 - 支持多种模型"""

    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model
        self.api_key = settings.OPENAI_API_KEY
        self.dimension = 1536 if "small" in model else 3072

    async def embed_text(self, text: str) -> List[float]:
        """单文本 Embedding"""
        results = await self.embed_texts([text])
        return results[0] if results else []

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """批量文本 Embedding"""
        if not self.api_key:
            logger.warning("OpenAI API key not configured, using mock embeddings")
            return [self._mock_embedding() for _ in texts]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "input": texts
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()

                embeddings = [item["embedding"] for item in data["data"]]
                return embeddings

        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            # 返回 mock embeddings 作为降级
            return [self._mock_embedding() for _ in texts]

    def _mock_embedding(self) -> List[float]:
        """Mock embedding（用于开发测试）"""
        import random
        return [random.random() for _ in range(self.dimension)]

    async def embed_query(self, query: str) -> List[float]:
        """查询 Embedding（可以添加特殊处理）"""
        # 可以在这里添加查询优化逻辑
        return await self.embed_text(query)
