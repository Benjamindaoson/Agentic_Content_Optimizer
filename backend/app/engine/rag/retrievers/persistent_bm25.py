"""
持久化 BM25 检索器

替代原来的内存级 rank-bm25，使用 Meilisearch 提供持久化的全文检索。
Meilisearch 内置了 BM25 变体算法 + 中文分词（jieba），
无需手动维护索引，支持增量更新，进程重启后索引不丢失。

降级方案：如果 Meilisearch 不可用，回退到内存级 BM25。
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class PersistentBM25:
    """
    持久化 BM25 检索器（Meilisearch 后端）

    用法：
        bm25 = PersistentBM25(index_name="xhs_references")
        await bm25.init()
        results = await bm25.search("护肤", limit=10)
    """

    def __init__(
        self,
        index_name: str = "reference_pool",
        meili_url: str = "http://localhost:7700",
        meili_key: Optional[str] = None,
    ):
        self.index_name = index_name
        self.meili_url = meili_url
        self.meili_key = meili_key
        self._client = None
        self._available = False

    async def init(self):
        """初始化 Meilisearch 连接和索引"""
        try:
            import meilisearch

            self._client = meilisearch.Client(
                self.meili_url,
                self.meili_key,
            )

            self._client.get_version()

            indexes = self._client.get_indexes()
            index_names = [idx.uid for idx in indexes.get("results", indexes) if hasattr(idx, 'uid')]

            if self.index_name not in index_names:
                self._client.create_index(
                    self.index_name,
                    {"primaryKey": "id"},
                )
                index = self._client.index(self.index_name)
                index.update_searchable_attributes([
                    "title", "content", "tags", "topic",
                ])
                index.update_filterable_attributes([
                    "platform", "niche", "created_at",
                ])
                logger.info(f"Created Meilisearch index: {self.index_name}")

            self._available = True
            logger.info(f"Meilisearch BM25 connected: {self.meili_url}/{self.index_name}")

        except ImportError:
            logger.warning("meilisearch package not installed, using in-memory BM25 fallback")
            self._available = False
        except Exception as e:
            logger.warning(f"Meilisearch unavailable ({e}), using in-memory BM25 fallback")
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    async def add_documents(self, documents: List[Dict[str, Any]]):
        """添加或更新文档到索引"""
        if not self._available or not self._client:
            return

        for doc in documents:
            if "id" not in doc:
                import hashlib
                doc["id"] = hashlib.md5(
                    (doc.get("title", "") + doc.get("content", "")[:100]).encode()
                ).hexdigest()

        try:
            index = self._client.index(self.index_name)
            index.add_documents(documents)
            logger.debug(f"Added {len(documents)} documents to Meilisearch")
        except Exception as e:
            logger.error(f"Failed to add documents to Meilisearch: {e}")

    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """全文检索（BM25 排序）"""
        if not self._available or not self._client:
            return []

        try:
            index = self._client.index(self.index_name)
            filter_str = None
            if filters:
                parts = [f'{k} = "{v}"' for k, v in filters.items()]
                filter_str = " AND ".join(parts)

            results = index.search(
                query,
                {"limit": limit, "filter": filter_str} if filter_str else {"limit": limit},
            )

            hits = []
            for hit in results.get("hits", []):
                hits.append({
                    "id": hit.get("id", ""),
                    "title": hit.get("title", ""),
                    "content": hit.get("content", ""),
                    "metadata": {
                        k: v for k, v in hit.items()
                        if k not in ("id", "title", "content", "_rankingScore")
                    },
                    "score": hit.get("_rankingScore", 0.0),
                })

            return hits

        except Exception as e:
            logger.warning(f"Meilisearch search failed: {e}")
            return []

    async def delete_index(self):
        """删除索引（测试用）"""
        if self._available and self._client:
            try:
                self._client.delete_index(self.index_name)
            except Exception:
                pass


class FallbackBM25:
    """内存级 BM25 降级方案（当 Meilisearch 不可用时）"""

    def __init__(self):
        self._corpus: List[Dict[str, Any]] = []
        self._bm25 = None

    def add_documents(self, documents: List[Dict[str, Any]]):
        self._corpus.extend(documents)
        self._rebuild_index()

    def _rebuild_index(self):
        try:
            from rank_bm25 import BM25Okapi
            import jieba

            tokenized = [
                list(jieba.cut(doc.get("content", "") + " " + doc.get("title", "")))
                for doc in self._corpus
            ]
            self._bm25 = BM25Okapi(tokenized)
        except ImportError:
            logger.warning("rank-bm25 or jieba not available")
            self._bm25 = None

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        if not self._bm25 or not self._corpus:
            return []

        try:
            import jieba
            tokenized_query = list(jieba.cut(query))
            scores = self._bm25.get_scores(tokenized_query)

            scored_docs = list(zip(scores, self._corpus))
            scored_docs.sort(key=lambda x: x[0], reverse=True)

            results = []
            for score, doc in scored_docs[:limit]:
                if score > 0:
                    results.append({**doc, "score": float(score)})

            return results
        except Exception as e:
            logger.warning(f"Fallback BM25 search failed: {e}")
            return []


async def get_bm25_retriever(
    index_name: str = "reference_pool",
) -> PersistentBM25:
    """获取 BM25 检索器（优先 Meilisearch，降级到内存）"""
    bm25 = PersistentBM25(index_name=index_name)
    await bm25.init()
    return bm25
