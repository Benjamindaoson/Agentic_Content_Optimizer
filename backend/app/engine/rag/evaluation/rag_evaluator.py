"""
RAG 评估器 - 检索质量评估

实现 NDCG、MRR、Precision、Recall 等指标
"""

from typing import List, Dict, Any, Optional
import numpy as np
from pydantic import BaseModel, Field
import logging

from app.engine.llm.unified import UnifiedLLM

logger = logging.getLogger(__name__)


class RAGMetrics(BaseModel):
    """RAG 评估指标"""
    ndcg_at_5: float = Field(..., description="NDCG@5")
    ndcg_at_10: float = Field(..., description="NDCG@10")
    mrr: float = Field(..., description="Mean Reciprocal Rank")
    precision_at_5: float = Field(..., description="Precision@5")
    precision_at_10: float = Field(..., description="Precision@10")
    recall_at_5: float = Field(..., description="Recall@5")
    recall_at_10: float = Field(..., description="Recall@10")
    map_score: float = Field(..., description="Mean Average Precision")


class RAGEvaluator:
    """RAG 检索质量评估器

    评估指标:
    - NDCG (Normalized Discounted Cumulative Gain): 考虑排序的相关性
    - MRR (Mean Reciprocal Rank): 第一个相关文档的排名倒数
    - Precision@K: 前 K 个结果中相关文档的比例
    - Recall@K: 前 K 个结果中召回的相关文档比例
    - MAP (Mean Average Precision): 平均精度均值
    """

    def __init__(self, llm: Optional[UnifiedLLM] = None):
        """初始化评估器

        Args:
            llm: LLM 实例，用于相关性判断
        """
        self.llm = llm or UnifiedLLM()

    def calculate_ndcg(
        self,
        retrieved_docs: List[Dict[str, Any]],
        relevance_scores: List[float],
        k: int = 10
    ) -> float:
        """计算 NDCG@k

        Args:
            retrieved_docs: 检索到的文档列表
            relevance_scores: 相关性评分列表（0-10）
            k: 截断位置

        Returns:
            float: NDCG@k 分数 (0-1)
        """
        if not relevance_scores or k <= 0:
            return 0.0

        # 截断到前 k 个
        relevance_scores = relevance_scores[:k]

        # 计算 DCG (Discounted Cumulative Gain)
        dcg = sum(
            (2 ** rel - 1) / np.log2(i + 2)
            for i, rel in enumerate(relevance_scores)
        )

        # 计算 IDCG (Ideal DCG)
        ideal_scores = sorted(relevance_scores, reverse=True)
        idcg = sum(
            (2 ** rel - 1) / np.log2(i + 2)
            for i, rel in enumerate(ideal_scores)
        )

        # 计算 NDCG
        if idcg == 0:
            return 0.0

        ndcg = dcg / idcg
        return round(ndcg, 4)

    def calculate_mrr(
        self,
        retrieved_docs: List[Dict[str, Any]],
        relevant_doc_ids: List[str]
    ) -> float:
        """计算 MRR (Mean Reciprocal Rank)

        Args:
            retrieved_docs: 检索到的文档列表
            relevant_doc_ids: 相关文档 ID 列表

        Returns:
            float: MRR 分数 (0-1)
        """
        if not retrieved_docs or not relevant_doc_ids:
            return 0.0

        # 找到第一个相关文档的位置
        for i, doc in enumerate(retrieved_docs):
            doc_id = doc.get("id") or doc.get("metadata", {}).get("id")
            if doc_id in relevant_doc_ids:
                return round(1.0 / (i + 1), 4)

        return 0.0

    def calculate_precision_at_k(
        self,
        retrieved_docs: List[Dict[str, Any]],
        relevant_doc_ids: List[str],
        k: int = 10
    ) -> float:
        """计算 Precision@K

        Args:
            retrieved_docs: 检索到的文档列表
            relevant_doc_ids: 相关文档 ID 列表
            k: 截断位置

        Returns:
            float: Precision@K (0-1)
        """
        if not retrieved_docs or k <= 0:
            return 0.0

        # 截断到前 k 个
        top_k_docs = retrieved_docs[:k]

        # 计算相关文档数量
        relevant_count = sum(
            1 for doc in top_k_docs
            if (doc.get("id") or doc.get("metadata", {}).get("id")) in relevant_doc_ids
        )

        precision = relevant_count / k
        return round(precision, 4)

    def calculate_recall_at_k(
        self,
        retrieved_docs: List[Dict[str, Any]],
        relevant_doc_ids: List[str],
        k: int = 10
    ) -> float:
        """计算 Recall@K

        Args:
            retrieved_docs: 检索到的文档列表
            relevant_doc_ids: 相关文档 ID 列表
            k: 截断位置

        Returns:
            float: Recall@K (0-1)
        """
        if not retrieved_docs or not relevant_doc_ids or k <= 0:
            return 0.0

        # 截断到前 k 个
        top_k_docs = retrieved_docs[:k]

        # 计算召回的相关文档数量
        recalled_count = sum(
            1 for doc in top_k_docs
            if (doc.get("id") or doc.get("metadata", {}).get("id")) in relevant_doc_ids
        )

        recall = recalled_count / len(relevant_doc_ids)
        return round(recall, 4)

    def calculate_map(
        self,
        retrieved_docs: List[Dict[str, Any]],
        relevant_doc_ids: List[str]
    ) -> float:
        """计算 MAP (Mean Average Precision)

        Args:
            retrieved_docs: 检索到的文档列表
            relevant_doc_ids: 相关文档 ID 列表

        Returns:
            float: MAP 分数 (0-1)
        """
        if not retrieved_docs or not relevant_doc_ids:
            return 0.0

        precisions = []
        relevant_count = 0

        for i, doc in enumerate(retrieved_docs):
            doc_id = doc.get("id") or doc.get("metadata", {}).get("id")
            if doc_id in relevant_doc_ids:
                relevant_count += 1
                precision_at_i = relevant_count / (i + 1)
                precisions.append(precision_at_i)

        if not precisions:
            return 0.0

        map_score = sum(precisions) / len(relevant_doc_ids)
        return round(map_score, 4)

    async def llm_judge_relevance(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        scale: int = 10
    ) -> List[float]:
        """使用 LLM 评估文档相关性

        Args:
            query: 查询文本
            documents: 文档列表
            scale: 评分范围 (默认 0-10)

        Returns:
            List[float]: 相关性评分列表
        """
        logger.info(f"LLM judging relevance for {len(documents)} documents")

        relevance_scores = []

        for doc in documents:
            # 提取文档文本
            doc_text = self._extract_doc_text(doc)

            # 构建评估 Prompt
            prompt = f"""你是一个专业的信息检索评估专家。请评估以下文档与查询的相关性。

**查询**: {query}

**文档**:
{doc_text[:500]}...

**评分标准**:
- 10分: 完全相关，直接回答查询
- 7-9分: 高度相关，包含大部分信息
- 4-6分: 部分相关，包含一些信息
- 1-3分: 弱相关，仅有少量相关信息
- 0分: 不相关

请只输出一个 0-{scale} 的数字，不要有其他内容。

评分:"""

            try:
                # 调用 LLM
                response = await self.llm.chat(
                    messages=[{"role": "user", "content": prompt}],
                    provider="claude",
                    model="haiku-4.5",  # 使用快速模型
                    temperature=0.1,
                    max_tokens=10
                )

                # 提取评分
                score = self._parse_score(response, scale)
                relevance_scores.append(score)

            except Exception as e:
                logger.error(f"LLM judge error: {e}")
                relevance_scores.append(5.0)  # 默认中等相关性

        logger.info(f"LLM judging complete: avg_score={np.mean(relevance_scores):.2f}")
        return relevance_scores

    def _extract_doc_text(self, doc: Dict[str, Any]) -> str:
        """提取文档文本"""
        # 尝试多种字段
        text = (
            doc.get("text") or
            doc.get("content") or
            doc.get("metadata", {}).get("text") or
            doc.get("metadata", {}).get("content") or
            str(doc)
        )
        return text[:1000]  # 限制长度

    def _parse_score(self, response: str, scale: int) -> float:
        """解析 LLM 响应中的评分"""
        import re

        # 提取数字
        numbers = re.findall(r'\d+\.?\d*', response)
        if numbers:
            score = float(numbers[0])
            # 确保在范围内
            score = max(0, min(scale, score))
            return score

        # 默认中等分数
        return scale / 2

    async def evaluate_retrieval_quality(
        self,
        query: str,
        retrieved_docs: List[Dict[str, Any]],
        ground_truth_docs: Optional[List[Dict[str, Any]]] = None,
        use_llm_judge: bool = True
    ) -> RAGMetrics:
        """综合评估检索质量

        Args:
            query: 查询文本
            retrieved_docs: 检索到的文档列表
            ground_truth_docs: Ground Truth 文档列表（可选）
            use_llm_judge: 是否使用 LLM 评估相关性

        Returns:
            RAGMetrics: 评估指标
        """
        logger.info(f"Evaluating retrieval quality for query: {query[:50]}...")

        # 1. 获取相关性评分
        if use_llm_judge:
            relevance_scores = await self.llm_judge_relevance(query, retrieved_docs)
        else:
            # 使用文档自带的分数
            relevance_scores = [
                doc.get("score", 5.0) for doc in retrieved_docs
            ]

        # 2. 获取相关文档 ID
        if ground_truth_docs:
            relevant_doc_ids = [
                doc.get("id") or doc.get("metadata", {}).get("id")
                for doc in ground_truth_docs
            ]
        else:
            # 如果没有 Ground Truth，使用高分文档作为相关文档
            relevant_doc_ids = [
                doc.get("id") or doc.get("metadata", {}).get("id")
                for i, doc in enumerate(retrieved_docs)
                if relevance_scores[i] >= 7.0
            ]

        # 3. 计算各项指标
        metrics = RAGMetrics(
            ndcg_at_5=self.calculate_ndcg(retrieved_docs, relevance_scores, k=5),
            ndcg_at_10=self.calculate_ndcg(retrieved_docs, relevance_scores, k=10),
            mrr=self.calculate_mrr(retrieved_docs, relevant_doc_ids),
            precision_at_5=self.calculate_precision_at_k(retrieved_docs, relevant_doc_ids, k=5),
            precision_at_10=self.calculate_precision_at_k(retrieved_docs, relevant_doc_ids, k=10),
            recall_at_5=self.calculate_recall_at_k(retrieved_docs, relevant_doc_ids, k=5),
            recall_at_10=self.calculate_recall_at_k(retrieved_docs, relevant_doc_ids, k=10),
            map_score=self.calculate_map(retrieved_docs, relevant_doc_ids)
        )

        logger.info(
            f"Evaluation complete: NDCG@10={metrics.ndcg_at_10:.4f}, "
            f"MRR={metrics.mrr:.4f}, MAP={metrics.map_score:.4f}"
        )

        return metrics

    async def compare_retrievers(
        self,
        query: str,
        retrievers: Dict[str, Any],
        ground_truth_docs: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, RAGMetrics]:
        """对比多个检索器的性能

        Args:
            query: 查询文本
            retrievers: 检索器字典 {name: retriever}
            ground_truth_docs: Ground Truth 文档

        Returns:
            Dict[str, RAGMetrics]: 各检索器的评估指标
        """
        logger.info(f"Comparing {len(retrievers)} retrievers")

        results = {}

        for name, retriever in retrievers.items():
            logger.info(f"Evaluating retriever: {name}")

            try:
                # 执行检索
                if hasattr(retriever, 'search'):
                    retrieved_docs = await retriever.search(query, limit=10)
                elif hasattr(retriever, 'retrieve'):
                    retrieved_docs = await retriever.retrieve(query, limit=10)
                else:
                    logger.error(f"Retriever {name} has no search/retrieve method")
                    continue

                # 评估
                metrics = await self.evaluate_retrieval_quality(
                    query=query,
                    retrieved_docs=retrieved_docs,
                    ground_truth_docs=ground_truth_docs,
                    use_llm_judge=True
                )

                results[name] = metrics

            except Exception as e:
                logger.error(f"Error evaluating {name}: {e}", exc_info=True)

        # 输出对比结果
        logger.info("\n=== Retriever Comparison ===")
        for name, metrics in results.items():
            logger.info(
                f"{name}: NDCG@10={metrics.ndcg_at_10:.4f}, "
                f"MRR={metrics.mrr:.4f}, MAP={metrics.map_score:.4f}"
            )

        return results
