#!/usr/bin/env python3
"""
Phase 2: 运行 RAG Benchmark

执行 RAGBenchmark，产出 NDCG/MRR 报告。
需要 Qdrant 和参考数据已就绪。

用法：
    python scripts/run_rag_benchmark.py [--output results/rag_benchmark.json]
    # 或: cd backend && PYTHONPATH=. python ../scripts/run_rag_benchmark.py
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# 确保 backend 在 path 中（脚本在 scripts/ 下）
project_root = Path(__file__).resolve().parent.parent
backend_dir = project_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


async def main():
    parser = argparse.ArgumentParser(description="Phase 2: RAG Benchmark")
    parser.add_argument("--output", type=str, default="results/rag_benchmark.json")
    parser.add_argument("--no-llm-judge", action="store_true", help="不使用 LLM 评估相关性（用文档分数）")
    args = parser.parse_args()

    from app.engine.rag.evaluation.benchmark import RAGBenchmark
    from app.engine.rag.retrievers.hybrid_retriever import HybridRetriever

    print("=" * 60)
    print("Phase 2: RAG Benchmark")
    print("=" * 60)

    benchmark = RAGBenchmark()
    benchmark.create_default_queries()
    hybrid = HybridRetriever()

    # Benchmark 期望 search(query, limit, filters)，HybridRetriever 有 hybrid_search
    async def search_adapter(query: str, limit: int = 10, filters: dict = None):
        return await hybrid.hybrid_search(query, limit=limit, filters=filters or {})

    hybrid.search = search_adapter
    retrievers = {"HybridRetriever": hybrid}

    print(f"Queries: {len(benchmark.queries)}")
    print(f"Retrievers: {list(retrievers.keys())}")
    print("Running benchmark...")

    results = await benchmark.run_benchmark(
        retrievers=retrievers,
        queries=benchmark.queries,
        use_llm_judge=not args.no_llm_judge,
    )

    report = benchmark.generate_report(results)

    # 保存
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nReport saved to {out_path}")

    # 打印 NDCG/MRR 摘要
    print("\n=== NDCG/MRR Summary ===")
    for name, stats in report.get("retriever_stats", {}).items():
        print(f"  {name}: NDCG@10={stats['avg_ndcg_at_10']:.4f}, MRR={stats['avg_mrr']:.4f}")

    return report


if __name__ == "__main__":
    asyncio.run(main())
