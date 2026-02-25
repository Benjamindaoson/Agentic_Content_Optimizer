"""
Phase 2: 评估维度定义与工具

评估维度（与 plan 一致）：
- 质量（Critic 分）：0-1，来自 CriticAgent
- 相关性（RAG 检索 NDCG）：来自 RAGEvaluator
- 成本（token 数）：估算
- 延迟（P95）：毫秒
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EvalDimensions:
    """评估维度"""
    quality_score: Optional[float] = None   # Critic 分 0-1
    ndcg_at_10: Optional[float] = None     # RAG 相关性
    mrr: Optional[float] = None             # RAG MRR
    token_count: Optional[int] = None       # 成本
    latency_ms: Optional[float] = None       # 延迟
    latency_p95_ms: Optional[float] = None  # P95 延迟（批量时）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quality_score": self.quality_score,
            "ndcg_at_10": self.ndcg_at_10,
            "mrr": self.mrr,
            "token_count": self.token_count,
            "latency_ms": self.latency_ms,
            "latency_p95_ms": self.latency_p95_ms,
        }


def compute_p95(values: List[float]) -> float:
    """计算 P95"""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * 0.95) - 1
    idx = max(0, idx)
    return sorted_vals[idx]


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数（中英混合约 2 字符/token）"""
    if not text:
        return 0
    return max(1, len(text) // 2)
