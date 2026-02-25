"""
RAG Benchmark - 检索系统基准测试

创建测试查询集并评估不同 RAG 策略的性能
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import logging
import json
from datetime import datetime

from app.engine.rag.evaluation.rag_evaluator import RAGEvaluator, RAGMetrics

logger = logging.getLogger(__name__)


class BenchmarkQuery(BaseModel):
    """基准测试查询"""
    query_id: str = Field(..., description="查询 ID")
    query: str = Field(..., description="查询文本")
    platform: str = Field(..., description="平台")
    category: str = Field(..., description="类别")
    ground_truth_ids: List[str] = Field(default_factory=list, description="相关文档 ID")
    difficulty: str = Field(default="medium", description="难度: easy/medium/hard")


class BenchmarkResult(BaseModel):
    """基准测试结果"""
    retriever_name: str
    query_id: str
    query: str
    metrics: RAGMetrics
    retrieved_count: int
    execution_time_ms: float


class RAGBenchmark:
    """RAG 基准测试

    功能:
    1. 创建测试查询集
    2. 评估不同 RAG 策略（Self-RAG, Adaptive RAG, CRAG）
    3. 生成性能报告
    """

    def __init__(self, evaluator: Optional[RAGEvaluator] = None):
        """初始化 Benchmark

        Args:
            evaluator: RAG 评估器实例
        """
        self.evaluator = evaluator or RAGEvaluator()
        self.queries: List[BenchmarkQuery] = []

    def create_default_queries(self) -> List[BenchmarkQuery]:
        """创建默认测试查询集

        覆盖不同平台、类别和难度
        """
        queries = [
            # 小红书 - 简单查询
            BenchmarkQuery(
                query_id="xhs_001",
                query="AI 写作工具推荐",
                platform="xiaohongshu",
                category="工具推荐",
                difficulty="easy"
            ),
            BenchmarkQuery(
                query_id="xhs_002",
                query="如何提高工作效率",
                platform="xiaohongshu",
                category="效率提升",
                difficulty="easy"
            ),

            # 小红书 - 中等查询
            BenchmarkQuery(
                query_id="xhs_003",
                query="适合新手的 AI 绘画工具对比",
                platform="xiaohongshu",
                category="工具对比",
                difficulty="medium"
            ),
            BenchmarkQuery(
                query_id="xhs_004",
                query="2024年最火的内容创作趋势",
                platform="xiaohongshu",
                category="趋势分析",
                difficulty="medium"
            ),

            # 小红书 - 困难查询
            BenchmarkQuery(
                query_id="xhs_005",
                query="如何用 AI 工具打造个人 IP 并实现商业变现",
                platform="xiaohongshu",
                category="商业策略",
                difficulty="hard"
            ),

            # 微博 - 简单查询
            BenchmarkQuery(
                query_id="wb_001",
                query="热门话题讨论",
                platform="weibo",
                category="热点",
                difficulty="easy"
            ),

            # 微博 - 中等查询
            BenchmarkQuery(
                query_id="wb_002",
                query="如何写出10万+阅读的微博",
                platform="weibo",
                category="写作技巧",
                difficulty="medium"
            ),

            # 抖音 - 简单查询
            BenchmarkQuery(
                query_id="dy_001",
                query="短视频拍摄技巧",
                platform="douyin",
                category="拍摄技巧",
                difficulty="easy"
            ),

            # 抖音 - 中等查询
            BenchmarkQuery(
                query_id="dy_002",
                query="如何提高短视频完播率和互动率",
                platform="douyin",
                category="运营策略",
                difficulty="medium"
            ),

            # 抖音 - 困难查询
            BenchmarkQuery(
                query_id="dy_003",
                query="从0到100万粉丝的抖音账号运营全流程",
                platform="douyin",
                category="账号运营",
                difficulty="hard"
            ),
        ]

        self.queries = queries
        logger.info(f"Created {len(queries)} benchmark queries")
        return queries

    async def run_benchmark(
        self,
        retrievers: Dict[str, Any],
        queries: Optional[List[BenchmarkQuery]] = None,
        use_llm_judge: bool = True
    ) -> List[BenchmarkResult]:
        """运行基准测试

        Args:
            retrievers: 检索器字典 {name: retriever}
            queries: 测试查询列表（如果为 None，使用默认查询）
            use_llm_judge: 是否使用 LLM 评估相关性

        Returns:
            List[BenchmarkResult]: 测试结果列表
        """
        if queries is None:
            queries = self.create_default_queries()

        logger.info(f"Running benchmark with {len(retrievers)} retrievers on {len(queries)} queries")

        results = []

        for query_obj in queries:
            logger.info(f"Testing query: {query_obj.query_id} - {query_obj.query}")

            for retriever_name, retriever in retrievers.items():
                try:
                    start_time = datetime.now()

                    # 执行检索
                    if hasattr(retriever, 'search'):
                        retrieved_docs = await retriever.search(
                            query_obj.query,
                            limit=10,
                            filters={"platform": query_obj.platform}
                        )
                    elif hasattr(retriever, 'retrieve'):
                        retrieved_docs = await retriever.retrieve(
                            query_obj.query,
                            limit=10
                        )
                    else:
                        logger.error(f"Retriever {retriever_name} has no search/retrieve method")
                        continue

                    execution_time = (datetime.now() - start_time).total_seconds() * 1000

                    # 评估
                    metrics = await self.evaluator.evaluate_retrieval_quality(
                        query=query_obj.query,
                        retrieved_docs=retrieved_docs,
                        ground_truth_docs=None,  # 暂时没有 Ground Truth
                        use_llm_judge=use_llm_judge
                    )

                    # 记录结果
                    result = BenchmarkResult(
                        retriever_name=retriever_name,
                        query_id=query_obj.query_id,
                        query=query_obj.query,
                        metrics=metrics,
                        retrieved_count=len(retrieved_docs),
                        execution_time_ms=execution_time
                    )

                    results.append(result)

                    logger.info(
                        f"{retriever_name} on {query_obj.query_id}: "
                        f"NDCG@10={metrics.ndcg_at_10:.4f}, "
                        f"time={execution_time:.0f}ms"
                    )

                except Exception as e:
                    logger.error(
                        f"Error testing {retriever_name} on {query_obj.query_id}: {e}",
                        exc_info=True
                    )

        logger.info(f"Benchmark complete: {len(results)} results")
        return results

    def generate_report(
        self,
        results: List[BenchmarkResult],
        output_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """生成基准测试报告

        Args:
            results: 测试结果列表
            output_file: 输出文件路径（可选）

        Returns:
            Dict: 报告数据
        """
        logger.info("Generating benchmark report")

        # 按检索器分组
        retriever_results = {}
        for result in results:
            if result.retriever_name not in retriever_results:
                retriever_results[result.retriever_name] = []
            retriever_results[result.retriever_name].append(result)

        # 计算每个检索器的平均指标
        retriever_stats = {}
        for retriever_name, retriever_results_list in retriever_results.items():
            ndcg_10_scores = [r.metrics.ndcg_at_10 for r in retriever_results_list]
            mrr_scores = [r.metrics.mrr for r in retriever_results_list]
            map_scores = [r.metrics.map_score for r in retriever_results_list]
            execution_times = [r.execution_time_ms for r in retriever_results_list]

            retriever_stats[retriever_name] = {
                "avg_ndcg_at_10": round(sum(ndcg_10_scores) / len(ndcg_10_scores), 4),
                "avg_mrr": round(sum(mrr_scores) / len(mrr_scores), 4),
                "avg_map": round(sum(map_scores) / len(map_scores), 4),
                "avg_execution_time_ms": round(sum(execution_times) / len(execution_times), 2),
                "num_queries": len(retriever_results_list)
            }

        # 排名
        ranked_by_ndcg = sorted(
            retriever_stats.items(),
            key=lambda x: x[1]["avg_ndcg_at_10"],
            reverse=True
        )

        # 生成报告
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_queries": len(set(r.query_id for r in results)),
            "total_retrievers": len(retriever_stats),
            "retriever_stats": retriever_stats,
            "ranking_by_ndcg": [
                {"rank": i + 1, "retriever": name, "ndcg_at_10": stats["avg_ndcg_at_10"]}
                for i, (name, stats) in enumerate(ranked_by_ndcg)
            ],
            "detailed_results": [
                {
                    "retriever": r.retriever_name,
                    "query_id": r.query_id,
                    "query": r.query,
                    "ndcg_at_10": r.metrics.ndcg_at_10,
                    "mrr": r.metrics.mrr,
                    "map": r.metrics.map_score,
                    "execution_time_ms": r.execution_time_ms
                }
                for r in results
            ]
        }

        # 输出到文件
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger.info(f"Report saved to {output_file}")

        # 打印摘要
        logger.info("\n=== Benchmark Report ===")
        logger.info(f"Total Queries: {report['total_queries']}")
        logger.info(f"Total Retrievers: {report['total_retrievers']}")
        logger.info("\nRanking by NDCG@10:")
        for item in report["ranking_by_ndcg"]:
            logger.info(f"  {item['rank']}. {item['retriever']}: {item['ndcg_at_10']:.4f}")

        return report

    async def compare_rag_strategies(
        self,
        hybrid_retriever,
        self_rag,
        adaptive_rag,
        crag,
        queries: Optional[List[BenchmarkQuery]] = None
    ) -> Dict[str, Any]:
        """对比不同 RAG 策略的性能

        Args:
            hybrid_retriever: 混合检索器
            self_rag: Self-RAG 实例
            adaptive_rag: Adaptive RAG 实例
            crag: CRAG 实例
            queries: 测试查询列表

        Returns:
            Dict: 对比报告
        """
        logger.info("Comparing RAG strategies: Hybrid, Self-RAG, Adaptive RAG, CRAG")

        retrievers = {
            "Hybrid Retriever": hybrid_retriever,
            "Self-RAG": self_rag,
            "Adaptive RAG": adaptive_rag,
            "CRAG": crag
        }

        # 运行基准测试
        results = await self.run_benchmark(retrievers, queries, use_llm_judge=True)

        # 生成报告
        report = self.generate_report(results)

        return report
