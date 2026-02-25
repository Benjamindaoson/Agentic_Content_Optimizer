"""
混合奖励模型 V2 - 升级版

改进:
1. 真实指标预测器（数据驱动）- 60% 权重
2. 降低 Critic 权重 - 30% 权重
3. 连续 Bonus 函数 - 10% 权重
4. 支持渐进式部署（影子模式、混合模式）

三层奖励结构:
- Layer 1: 真实世界奖励（CTR/完播率/互动率/转化率）
- Layer 2: 内容质量奖励（Critic + 结构评分）
- Layer 3: 系统健康奖励（多样性 + 新颖度 + GEO）
"""

import logging
from typing import Dict, List, Optional, Any
import numpy as np
from dataclasses import dataclass

from app.ml.rl.real_metric_predictors import RealMetricPredictorEnsemble

logger = logging.getLogger(__name__)


@dataclass
class RewardBreakdown:
    """奖励分解"""
    total_reward: float
    real_world_reward: float
    quality_reward: float
    system_health_reward: float
    real_metrics: Dict[str, float]
    quality_components: Dict[str, float]
    health_components: Dict[str, float]


class HybridRewardModelV2:
    """
    混合奖励模型 V2

    核心改进:
    1. 真实指标预测（数据驱动）
    2. 连续新颖度评分
    3. 三层奖励结构
    """

    def __init__(
        self,
        predictor_model_dir: Optional[str] = None,
        weights: Optional[Dict[str, float]] = None,
        real_metric_weights: Optional[Dict[str, float]] = None,
        deployment_mode: str = "full",  # "shadow", "hybrid", "full"
        reward_shaping: bool = True,  # Enable reward shaping
        reward_scale: float = 10.0  # Scale factor for rewards
    ):
        """
        初始化

        Args:
            predictor_model_dir: 预测模型目录
            weights: 三层权重 {'real_world': 0.6, 'quality': 0.3, 'system_health': 0.1}
            real_metric_weights: 真实指标权重 {'ctr': 0.3, 'completion': 0.3, 'engagement': 0.2, 'conversion': 0.2}
            deployment_mode: 部署模式
            reward_shaping: 是否启用奖励塑形
            reward_scale: 奖励缩放因子
        """
        # 加载预测器
        self.predictor_ensemble = RealMetricPredictorEnsemble(predictor_model_dir)

        # 三层权重
        self.weights = weights or {
            'real_world': 0.6,
            'quality': 0.3,
            'system_health': 0.1
        }

        # 真实指标权重
        self.real_metric_weights = real_metric_weights or {
            'ctr': 0.3,
            'completion': 0.3,
            'engagement': 0.2,
            'conversion': 0.2
        }

        # 部署模式
        self.deployment_mode = deployment_mode
        self.hybrid_alpha = 0.5  # 混合模式的插值系数

        # 奖励塑形参数
        self.reward_shaping = reward_shaping
        self.reward_scale = reward_scale

        # 历史 embeddings（用于新颖度计算）
        self.history_embeddings: List[np.ndarray] = []
        self.max_history = 100

        logger.info(f"✅ HybridRewardModelV2 初始化完成 (模式: {deployment_mode}, 奖励塑形: {reward_shaping})")

    def calculate_reward(
        self,
        content: Dict[str, Any],
        context: Dict[str, Any],
        critic_eval: Optional[Dict[str, Any]] = None,
        action: Optional[Dict[str, Any]] = None
    ) -> RewardBreakdown:
        """
        计算奖励

        Args:
            content: 生成的内容
            context: 上下文信息
            critic_eval: Critic 评估结果
            action: 动作信息

        Returns:
            奖励分解
        """
        # 1. 真实世界奖励（数据驱动）
        real_reward, real_metrics = self._calculate_real_world_reward(content, action)

        # 2. 内容质量奖励（混合）
        quality_reward, quality_components = self._calculate_quality_reward(content, critic_eval)

        # 3. 系统健康奖励（连续函数）
        health_reward, health_components = self._calculate_system_health_reward(content, context)

        # 总奖励
        total = (
            self.weights['real_world'] * real_reward +
            self.weights['quality'] * quality_reward +
            self.weights['system_health'] * health_reward
        )

        # 奖励塑形：放大信号差异
        if self.reward_shaping:
            total = self._apply_reward_shaping(total)

        return RewardBreakdown(
            total_reward=total,
            real_world_reward=real_reward,
            quality_reward=quality_reward,
            system_health_reward=health_reward,
            real_metrics=real_metrics,
            quality_components=quality_components,
            health_components=health_components
        )

    def _calculate_real_world_reward(
        self,
        content: Dict[str, Any],
        action: Optional[Dict[str, Any]]
    ) -> tuple[float, Dict[str, float]]:
        """
        计算真实世界奖励

        基于预测的真实用户行为指标
        """
        # 预测所有指标
        metrics = self.predictor_ensemble.predict_all(content, action)

        # 加权求和
        reward = (
            self.real_metric_weights['ctr'] * metrics['ctr'] +
            self.real_metric_weights['completion'] * metrics['completion_rate'] +
            self.real_metric_weights['engagement'] * metrics['engagement_rate'] +
            self.real_metric_weights['conversion'] * metrics['conversion_rate']
        )

        return reward, metrics

    def _calculate_quality_reward(
        self,
        content: Dict[str, Any],
        critic_eval: Optional[Dict[str, Any]]
    ) -> tuple[float, Dict[str, float]]:
        """
        计算内容质量奖励

        混合 Critic 评分和结构评分
        """
        components = {}

        # 1. Critic 评分（如果有）
        if critic_eval:
            critic_score = critic_eval.get('overall_score', 0.5)
        else:
            critic_score = 0.5
        components['critic_score'] = critic_score

        # 2. 结构评分
        structure_score = self._calculate_structure_score(content)
        components['structure_score'] = structure_score

        # 混合
        quality_reward = 0.5 * critic_score + 0.5 * structure_score

        return quality_reward, components

    def _calculate_structure_score(self, content: Dict[str, Any]) -> float:
        """
        计算结构评分

        基于内容的结构特征
        """
        score = 0.0
        count = 0

        hook = content.get('hook', '')
        body = content.get('body', '')
        cta = content.get('cta', '')

        # 1. 长度合理性
        if 10 <= len(hook) <= 100:
            score += 1.0
            count += 1

        if 50 <= len(body) <= 500:
            score += 1.0
            count += 1

        if 5 <= len(cta) <= 50:
            score += 1.0
            count += 1

        # 2. 完整性
        if hook and body and cta:
            score += 1.0
            count += 1

        # 3. 多样性（不同部分不应太相似）
        if hook and body:
            similarity = self._simple_similarity(hook, body)
            if similarity < 0.5:  # 不太相似
                score += 1.0
                count += 1

        return score / count if count > 0 else 0.5

    def _simple_similarity(self, text1: str, text2: str) -> float:
        """Compute text similarity using cosine similarity on embeddings."""
        emb1 = self._get_embedding({"hook": text1})
        emb2 = self._get_embedding({"hook": text2})
        dot = np.dot(emb1, emb2)
        return float(np.clip(dot, 0.0, 1.0))

    def _calculate_system_health_reward(
        self,
        content: Dict[str, Any],
        context: Dict[str, Any]
    ) -> tuple[float, Dict[str, float]]:
        """
        计算系统健康奖励

        包括多样性、新颖度、GEO 适配
        """
        components = {}

        # 1. 多样性评分
        diversity_score = self._calculate_diversity_score(content, context)
        components['diversity'] = diversity_score

        # 2. 新颖度评分（连续函数）
        novelty_score = self._calculate_novelty_score(content)
        components['novelty'] = novelty_score

        # 3. GEO 适配评分
        geo_score = self._calculate_geo_score(content, context)
        components['geo'] = geo_score

        # 加权求和
        health_reward = (
            0.4 * diversity_score +
            0.4 * novelty_score +
            0.2 * geo_score
        )

        return health_reward, components

    def _calculate_diversity_score(
        self,
        content: Dict[str, Any],
        context: Dict[str, Any]
    ) -> float:
        """
        计算多样性评分

        基于动作类型的多样性
        """
        # 简单实现：检查是否使用了不同的模板
        action = context.get('action', {})
        hook_id = action.get('hook_id', 0)
        body_id = action.get('body_id', 0)
        cta_id = action.get('cta_id', 0)

        # 如果使用了不同的组合，给予奖励
        if hook_id != body_id and body_id != cta_id:
            return 0.8
        elif hook_id != body_id or body_id != cta_id:
            return 0.6
        else:
            return 0.4

    def _calculate_novelty_score(self, content: Dict[str, Any]) -> float:
        """
        计算新颖度评分（连续函数）

        基于 embedding 距离，避免阶梯式奖励
        """
        # 获取当前内容的 embedding
        current_emb = self._get_embedding(content)

        # 如果没有历史，返回高新颖度
        if not self.history_embeddings:
            self.history_embeddings.append(current_emb)
            return 1.0

        # 计算与历史内容的平均距离
        distances = [
            self._cosine_distance(current_emb, hist_emb)
            for hist_emb in self.history_embeddings[-50:]  # 只看最近 50 个
        ]

        avg_distance = np.mean(distances)

        # 归一化到 [0, 1]，使用连续函数
        # 距离越大，新颖度越高
        novelty = min(avg_distance / 0.5, 1.0)  # 0.5 是归一化因子

        # 更新历史
        self.history_embeddings.append(current_emb)
        if len(self.history_embeddings) > self.max_history:
            self.history_embeddings.pop(0)

        return novelty

    def _get_embedding(self, content: Dict[str, Any]) -> np.ndarray:
        """
        获取内容的 embedding using StateEncoder for consistent representation.
        """
        try:
            from app.ml.rl.networks import StateEncoder
            encoder = StateEncoder(state_dim=128)
            tensor = encoder.encode(content)
            emb = tensor.numpy()
            norm = np.linalg.norm(emb)
            if norm > 0:
                emb = emb / norm
            return emb
        except Exception:
            # Fallback: bag-of-words hash
            text = f"{content.get('hook', '')} {content.get('body', '')} {content.get('cta', '')}"
            words = text.split()
            vocab_size = 128
            embedding = np.zeros(vocab_size)
            for word in words:
                idx = hash(word) % vocab_size
                embedding[idx] += 1
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            return embedding

    def _cosine_distance(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """计算余弦距离"""
        dot_product = np.dot(emb1, emb2)
        return 1.0 - dot_product  # 余弦距离 = 1 - 余弦相似度

    def _calculate_geo_score(
        self,
        content: Dict[str, Any],
        context: Dict[str, Any]
    ) -> float:
        """
        计算 GEO 适配评分

        Uses keyword extraction + semantic matching for geo relevance.
        """
        target_geo = context.get('target_geo', 'CN')
        text = f"{content.get('hook', '')} {content.get('body', '')} {content.get('cta', '')}"

        geo_keywords = {
            'CN': ['中国', '国内', '小红书', '抖音', '快手', '微博', '淘宝', '京东',
                    '人民', '北京', '上海', '广州', '深圳', '杭州'],
            'US': ['美国', 'US', 'America', 'English', 'TikTok', 'Instagram'],
            'EU': ['欧洲', 'Europe', 'EU', 'European'],
            'JP': ['日本', 'Japan', '东京', 'Tokyo'],
            'KR': ['韩国', 'Korea', '首尔', 'Seoul'],
        }

        keywords = geo_keywords.get(target_geo, [])
        if not keywords:
            return 0.5

        # Count keyword matches
        match_count = sum(1 for kw in keywords if kw in text)
        keyword_score = min(match_count / max(len(keywords) * 0.3, 1), 1.0)

        # Semantic matching: compare content embedding with geo reference
        content_emb = self._get_embedding(content)
        geo_ref = self._get_embedding({"hook": " ".join(keywords[:5])})
        semantic_score = float(np.clip(np.dot(content_emb, geo_ref), 0, 1))

        # Weighted combination
        score = 0.6 * keyword_score + 0.4 * semantic_score
        return float(np.clip(score, 0.0, 1.0))

    def set_deployment_mode(self, mode: str, alpha: float = 0.5):
        """
        设置部署模式

        Args:
            mode: "shadow", "hybrid", "full"
            alpha: 混合模式的插值系数（0-1）
        """
        self.deployment_mode = mode
        self.hybrid_alpha = alpha
        logger.info(f"部署模式已设置为: {mode} (alpha={alpha})")

    def calculate_hybrid_reward(
        self,
        content: Dict[str, Any],
        context: Dict[str, Any],
        critic_eval: Optional[Dict[str, Any]],
        action: Optional[Dict[str, Any]],
        old_reward: float
    ) -> float:
        """
        计算混合奖励（用于渐进式部署）

        Args:
            content: 内容
            context: 上下文
            critic_eval: Critic 评估
            action: 动作
            old_reward: 旧模型的奖励

        Returns:
            混合奖励
        """
        if self.deployment_mode == "shadow":
            # 影子模式：只记录，不使用
            new_breakdown = self.calculate_reward(content, context, critic_eval, action)
            logger.debug(f"影子模式 - 新奖励: {new_breakdown.total_reward}, 旧奖励: {old_reward}")
            return old_reward

        elif self.deployment_mode == "hybrid":
            # 混合模式：线性插值
            new_breakdown = self.calculate_reward(content, context, critic_eval, action)
            hybrid_reward = (
                self.hybrid_alpha * new_breakdown.total_reward +
                (1 - self.hybrid_alpha) * old_reward
            )
            logger.debug(f"混合模式 (alpha={self.hybrid_alpha}) - 混合奖励: {hybrid_reward}")
            return hybrid_reward

        else:  # "full"
            # 完全模式：只使用新模型
            new_breakdown = self.calculate_reward(content, context, critic_eval, action)
            return new_breakdown.total_reward

    def _apply_reward_shaping(self, reward: float) -> float:
        """
        应用奖励塑形，放大信号差异

        使用非线性变换放大好内容和差内容之间的差异：
        - 对于高质量内容（>0.7），给予额外奖励
        - 对于低质量内容（<0.3），给予惩罚
        - 中等质量内容保持线性

        Args:
            reward: 原始奖励 [0, 1]

        Returns:
            塑形后的奖励，缩放到 [-reward_scale, reward_scale]
        """
        # 1. 非线性变换：使用 tanh 放大差异
        # 将 [0, 1] 映射到 [-3, 3]，然后通过 tanh 压缩到 [-1, 1]
        centered = (reward - 0.5) * 6  # [-3, 3]
        shaped = np.tanh(centered)  # [-1, 1]

        # 2. 缩放到目标范围
        scaled = shaped * self.reward_scale

        # 3. 对极端值给予额外奖励/惩罚
        if reward > 0.8:
            # 高质量内容：额外 20% 奖励
            scaled *= 1.2
        elif reward < 0.2:
            # 低质量内容：额外 20% 惩罚
            scaled *= 1.2

        return float(scaled)

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'deployment_mode': self.deployment_mode,
            'hybrid_alpha': self.hybrid_alpha,
            'history_size': len(self.history_embeddings),
            'weights': self.weights,
            'real_metric_weights': self.real_metric_weights,
            'reward_shaping': self.reward_shaping,
            'reward_scale': self.reward_scale
        }
