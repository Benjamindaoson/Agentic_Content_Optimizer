"""
RAG 监控 API

提供 RAG 检索质量监控和评估端点
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging

from app.engine.rag.evaluation import RAGEvaluator, RAGMetrics, RAGBenchmark
from app.engine.rag.retrievers.hybrid_retriever import HybridRetriever
from app.engine.rag.advanced_rag import SelfRAG, AdaptiveRAG, CorrectiveRAG

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag", tags=["rag-monitoring"])


class EvaluateRequest(BaseModel):
    """评估请求"""
    query: str = Field(..., description="查询文本")
    retrieved_docs: List[Dict[str, Any]] = Field(..., description="检索到的文档")
    use_llm_judge: bool = Field(default=True, description="是否使用 LLM 评估相关性")


class BenchmarkRequest(BaseModel):
    """基准测试请求"""
    retriever_types: List[str] = Field(
        default=["hybrid", "self_rag", "adaptive_rag", "crag"],
        description="要测试的检索器类型"
    )
    use_default_queries: bool = Field(default=True, description="使用默认查询集")
    custom_queries: Optional[List[Dict[str, Any]]] = Field(None, description="自定义查询")


# 全局实例（懒加载）
_evaluator_instance = None
_benchmark_instance = None


def get_evaluator() -> RAGEvaluator:
    """获取评估器实例"""
    global _evaluator_instance
    if _evaluator_instance is None:
        _evaluator_instance = RAGEvaluator()
        logger.info("RAGEvaluator initialized")
    return _evaluator_instance


def get_benchmark() -> RAGBenchmark:
    """获取 Benchmark 实例"""
    global _benchmark_instance
    if _benchmark_instance is None:
        _benchmark_instance = RAGBenchmark(evaluator=get_evaluator())
        logger.info("RAGBenchmark initialized")
    return _benchmark_instance


@router.post("/evaluate", response_model=RAGMetrics)
async def evaluate_retrieval(request: EvaluateRequest):
    """评估检索质量

    计算 NDCG、MRR、Precision、Recall 等指标
    """
    try:
        evaluator = get_evaluator()

        metrics = await evaluator.evaluate_retrieval_quality(
            query=request.query,
            retrieved_docs=request.retrieved_docs,
            ground_truth_docs=None,
            use_llm_judge=request.use_llm_judge
        )

        return metrics

    except Exception as e:
        logger.error(f"Evaluation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_rag_metrics():
    """获取 RAG 系统的实时指标

    返回最近的检索质量统计
    """
    try:
        # 这里可以从数据库或缓存中获取历史指标
        # 暂时返回模拟数据
        return {
            "timestamp": "2026-02-14T12:00:00",
            "period": "last_24h",
            "metrics": {
                "avg_ndcg_at_10": 0.78,
                "avg_mrr": 0.82,
                "avg_map": 0.75,
                "avg_precision_at_5": 0.85,
                "avg_recall_at_10": 0.72,
                "total_queries": 1250,
                "avg_latency_ms": 245
            },
            "by_platform": {
                "xiaohongshu": {
                    "avg_ndcg_at_10": 0.80,
                    "queries": 650
                },
                "weibo": {
                    "avg_ndcg_at_10": 0.76,
                    "queries": 350
                },
                "douyin": {
                    "avg_ndcg_at_10": 0.77,
                    "queries": 250
                }
            }
        }

    except Exception as e:
        logger.error(f"Get metrics error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/benchmark")
async def run_benchmark(request: BenchmarkRequest, background_tasks: BackgroundTasks):
    """运行 RAG 基准测试

    对比不同检索策略的性能
    """
    try:
        benchmark = get_benchmark()

        # 创建检索器实例
        retrievers = {}

        if "hybrid" in request.retriever_types:
            retrievers["Hybrid Retriever"] = HybridRetriever()

        if "self_rag" in request.retriever_types:
            retrievers["Self-RAG"] = SelfRAG(HybridRetriever())

        if "adaptive_rag" in request.retriever_types:
            retrievers["Adaptive RAG"] = AdaptiveRAG(HybridRetriever())

        if "crag" in request.retriever_types:
            retrievers["CRAG"] = CRAG(HybridRetriever())

        # 准备查询
        queries = None
        if not request.use_default_queries and request.custom_queries:
            from app.engine.rag.evaluation.benchmark import BenchmarkQuery
            queries = [BenchmarkQuery(**q) for q in request.custom_queries]

        # 运行基准测试
        results = await benchmark.run_benchmark(
            retrievers=retrievers,
            queries=queries,
            use_llm_judge=True
        )

        # 生成报告
        report = benchmark.generate_report(results)

        return {
            "success": True,
            "message": f"Benchmark completed with {len(results)} results",
            "report": report
        }

    except Exception as e:
        logger.error(f"Benchmark error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/benchmark/queries")
async def get_benchmark_queries():
    """获取默认的基准测试查询集"""
    try:
        benchmark = get_benchmark()
        queries = benchmark.create_default_queries()

        return {
            "total": len(queries),
            "queries": [
                {
                    "query_id": q.query_id,
                    "query": q.query,
                    "platform": q.platform,
                    "category": q.category,
                    "difficulty": q.difficulty
                }
                for q in queries
            ]
        }

    except Exception as e:
        logger.error(f"Get queries error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
async def compare_retrievers(
    query: str,
    retriever_types: List[str] = ["hybrid", "self_rag", "adaptive_rag", "crag"]
):
    """对比不同检索器在单个查询上的表现"""
    try:
        evaluator = get_evaluator()

        # 创建检索器实例
        retrievers = {}

        if "hybrid" in retriever_types:
            retrievers["Hybrid"] = HybridRetriever()

        if "self_rag" in retriever_types:
            retrievers["Self-RAG"] = SelfRAG(HybridRetriever())

        if "adaptive_rag" in retriever_types:
            retrievers["Adaptive"] = AdaptiveRAG(HybridRetriever())

        if "crag" in retriever_types:
            retrievers["CRAG"] = CRAG(HybridRetriever())

        # 对比检索器
        results = await evaluator.compare_retrievers(
            query=query,
            retrievers=retrievers,
            ground_truth_docs=None
        )

        # 格式化结果
        comparison = {
            "query": query,
            "retrievers": {
                name: {
                    "ndcg_at_10": metrics.ndcg_at_10,
                    "mrr": metrics.mrr,
                    "map": metrics.map_score,
                    "precision_at_5": metrics.precision_at_5,
                    "recall_at_10": metrics.recall_at_10
                }
                for name, metrics in results.items()
            }
        }

        # 找出最佳检索器
        best_retriever = max(
            results.items(),
            key=lambda x: x[1].ndcg_at_10
        )

        comparison["best_retriever"] = {
            "name": best_retriever[0],
            "ndcg_at_10": best_retriever[1].ndcg_at_10
        }

        return comparison

    except Exception as e:
        logger.error(f"Compare error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
