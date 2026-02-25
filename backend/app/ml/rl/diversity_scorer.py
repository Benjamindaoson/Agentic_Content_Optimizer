"""
多样性评分模块

基于余弦相似度 + 去重复 + 可控探索强度的多样性计算

核心功能:
1. 内容重复检测（embedding 相似度）
2. 策略重复惩罚（防止策略塌缩）
3. 近邻查询优化（Qdrant 加速）
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Tuple, Dict, Any
import numpy as np
import logging

logger = logging.getLogger(__name__)


def _l2_normalize(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """L2 归一化"""
    x = x.astype(np.float32)
    n = np.linalg.norm(x)
    return x / (n + eps)


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """计算两个向量的余弦相似度"""
    a = _l2_normalize(a)
    b = _l2_normalize(b)
    return float(np.dot(a, b))


def cosine_sims(vec: np.ndarray, mat: np.ndarray) -> np.ndarray:
    """
    计算一个向量与矩阵中所有向量的余弦相似度

    Args:
        vec: [d] 查询向量
        mat: [n, d] 参考向量矩阵

    Returns:
        [n] 相似度数组
    """
    vec = _l2_normalize(vec)
    mat = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-12)
    return mat @ vec


@dataclass
class DiversityConfig:
    """多样性配置"""

    # 相似度阈值：超过则视为"过像"
    near_dup_threshold: float = 0.92

    # 惩罚强度：近重复时把分数压到接近 0
    near_dup_penalty: float = 0.85  # 0~1，越大惩罚越狠

    # 参考池最多取多少条做相似度对比（工程上防止太慢）
    max_refs: int = 200

    # 取 top-k 最相似的均值作为"相似度指标"（比只看 max 更稳）
    topk: int = 5

    # 策略重复惩罚：同一 (H,B,C) 出现越多，额外扣分越多
    strategy_freq_penalty: float = 0.25  # 0~1

    # 频率惩罚起效阈值（出现 >= 多少次开始扣）
    strategy_freq_start: int = 3


class DiversityScorer:
    """
    多样性评分器

    功能:
    1. 基于 embedding 的内容相似度检测
    2. 策略频率统计和惩罚
    3. 可选的 Qdrant 近邻查询优化
    """

    def __init__(
        self,
        embed_fn: Callable[[str], np.ndarray],
        config: Optional[DiversityConfig] = None,
        use_qdrant: bool = False,
        qdrant_client: Optional[Any] = None,
        qdrant_collection: str = "diversity_pool"
    ):
        """
        初始化

        Args:
            embed_fn: 文本 embedding 函数
            config: 多样性配置
            use_qdrant: 是否使用 Qdrant 加速
            qdrant_client: Qdrant 客户端
            qdrant_collection: Qdrant 集合名称
        """
        self.embed_fn = embed_fn
        self.config = config or DiversityConfig()
        self.use_qdrant = use_qdrant
        self.qdrant_client = qdrant_client
        self.qdrant_collection = qdrant_collection

        # 策略频率统计
        self.strategy_counts: Dict[Tuple[str, str, str], int] = {}

        # 本地缓存（当不使用 Qdrant 时）
        self.ref_texts: List[str] = []
        self.ref_embeds: Optional[np.ndarray] = None

        logger.info(f"✅ DiversityScorer 初始化完成 (use_qdrant={use_qdrant})")

    def compute_diversity_score(
        self,
        text: str,
        strategy_triplet: Tuple[str, str, str],
        ref_texts: Optional[Iterable[str]] = None,
        ref_embeds: Optional[np.ndarray] = None
    ) -> float:
        """
        计算多样性分数

        Args:
            text: 当前内容文本
            strategy_triplet: (hook_id, body_id, cta_id)
            ref_texts: 参考文本列表（可选）
            ref_embeds: 参考 embeddings（可选）

        Returns:
            多样性分数 [0, 1]，越接近 1 表示越新/不同
        """
        # 1. 准备参考数据
        if ref_texts is None:
            ref_texts = self.ref_texts

        ref_texts_list = list(ref_texts)

        if len(ref_texts_list) == 0:
            # 没有参考，完全新颖
            base_div = 1.0
        else:
            # 使用 Qdrant 或本地计算
            if self.use_qdrant and self.qdrant_client:
                base_div = self._compute_diversity_with_qdrant(text)
            else:
                base_div = self._compute_diversity_local(text, ref_texts_list, ref_embeds)

        # 2. 策略频率惩罚
        freq = self.strategy_counts.get(strategy_triplet, 0)
        if freq >= self.config.strategy_freq_start:
            delta = freq - self.config.strategy_freq_start + 1
            smooth = 1.0 - np.exp(-0.6 * delta)
            base_div = base_div * (1.0 - self.config.strategy_freq_penalty * float(smooth))

        return float(np.clip(base_div, 0.0, 1.0))

    def _compute_diversity_local(
        self,
        text: str,
        ref_texts_list: List[str],
        ref_embeds: Optional[np.ndarray]
    ) -> float:
        """本地计算多样性（不使用 Qdrant）"""

        # 截断参考列表
        ref_texts_list = ref_texts_list[-self.config.max_refs:]

        # 准备参考向量
        if ref_embeds is None:
            ref_vecs = np.vstack([_l2_normalize(self.embed_fn(t)) for t in ref_texts_list])
        else:
            ref_vecs = ref_embeds[-len(ref_texts_list):]
            ref_vecs = ref_vecs.astype(np.float32)
            ref_vecs = ref_vecs / (np.linalg.norm(ref_vecs, axis=1, keepdims=True) + 1e-12)

        # 计算当前文本的 embedding
        v = _l2_normalize(self.embed_fn(text))

        # 计算相似度
        sims = cosine_sims(v, ref_vecs)

        # 用 top-k 最相似均值衡量"像不像"
        topk = min(self.config.topk, sims.shape[0])
        topk_mean = float(np.mean(np.partition(sims, -topk)[-topk:]))

        # 基础多样性 = 1 - 相似度
        base_div = float(np.clip(1.0 - topk_mean, 0.0, 1.0))

        # 近重复强惩罚
        max_sim = float(np.max(sims))
        if max_sim >= self.config.near_dup_threshold:
            base_div = base_div * (1.0 - self.config.near_dup_penalty)

        return base_div

    def _compute_diversity_with_qdrant(self, text: str) -> float:
        """使用 Qdrant 计算多样性（加速版）"""

        try:
            # 计算 embedding
            v = self.embed_fn(text)

            # Qdrant 近邻查询
            search_result = self.qdrant_client.search(
                collection_name=self.qdrant_collection,
                query_vector=v.tolist(),
                limit=self.config.topk
            )

            if not search_result:
                return 1.0

            # 提取相似度分数
            sims = [hit.score for hit in search_result]
            topk_mean = float(np.mean(sims))

            # 基础多样性
            base_div = float(np.clip(1.0 - topk_mean, 0.0, 1.0))

            # 近重复惩罚
            max_sim = float(np.max(sims))
            if max_sim >= self.config.near_dup_threshold:
                base_div = base_div * (1.0 - self.config.near_dup_penalty)

            return base_div

        except Exception as e:
            logger.warning(f"Qdrant 查询失败，降级到本地计算: {e}")
            return self._compute_diversity_local(text, self.ref_texts, self.ref_embeds)

    def update_strategy_count(self, strategy_triplet: Tuple[str, str, str]):
        """更新策略频率统计"""
        self.strategy_counts[strategy_triplet] = self.strategy_counts.get(strategy_triplet, 0) + 1

    def add_reference(self, text: str, embedding: Optional[np.ndarray] = None):
        """添加参考文本到本地缓存"""
        self.ref_texts.append(text)

        if embedding is not None:
            if self.ref_embeds is None:
                self.ref_embeds = embedding.reshape(1, -1)
            else:
                self.ref_embeds = np.vstack([self.ref_embeds, embedding.reshape(1, -1)])

        # 限制缓存大小
        if len(self.ref_texts) > self.config.max_refs * 2:
            # 保留最近的
            self.ref_texts = self.ref_texts[-self.config.max_refs:]
            if self.ref_embeds is not None:
                self.ref_embeds = self.ref_embeds[-self.config.max_refs:]

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'total_strategies': len(self.strategy_counts),
            'total_references': len(self.ref_texts),
            'most_used_strategies': sorted(
                self.strategy_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10],
            'config': {
                'near_dup_threshold': self.config.near_dup_threshold,
                'near_dup_penalty': self.config.near_dup_penalty,
                'strategy_freq_penalty': self.config.strategy_freq_penalty,
                'strategy_freq_start': self.config.strategy_freq_start
            }
        }


def diversity_bonus_from_score(diversity_score: float, max_bonus: float = 0.2) -> float:
    """
    从多样性分数计算奖励 bonus

    Args:
        diversity_score: 多样性分数 [0, 1]
        max_bonus: 最大 bonus

    Returns:
        bonus 值
    """
    return float(np.clip(diversity_score, 0.0, 1.0) * max_bonus)
