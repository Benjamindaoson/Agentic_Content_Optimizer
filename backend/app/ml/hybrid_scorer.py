"""
混合评分器

结合LightGBM和LLM，提供稳定的评分
"""

import logging
from typing import Dict, Optional
from datetime import datetime
import asyncio

from sqlalchemy.orm import Session
from app.ml.lightgbm_trainer import LightGBMTrainer
from app.ml.feature_extractor import FeatureExtractor

logger = logging.getLogger(__name__)


class HybridScorer:
    """
    混合评分器

    功能：
    1. 优先使用LightGBM（快速、稳定、低成本）
    2. LLM作为补充（处理边缘情况）
    3. 自适应权重调整
    4. 降级策略
    """

    def __init__(
        self,
        lgb_trainer: LightGBMTrainer,
        feature_extractor: FeatureExtractor,
        lgb_weight: float = 0.7,
        llm_weight: float = 0.3,
        use_llm_threshold: float = 0.5  # 置信度低于此值时使用LLM
    ):
        """
        Args:
            lgb_trainer: LightGBM训练器
            feature_extractor: 特征提取器
            lgb_weight: LightGBM权重
            llm_weight: LLM权重
            use_llm_threshold: 使用LLM的置信度阈值
        """
        self.lgb_trainer = lgb_trainer
        self.feature_extractor = feature_extractor
        self.lgb_weight = lgb_weight
        self.llm_weight = llm_weight
        self.use_llm_threshold = use_llm_threshold

        # 统计信息
        self.stats = {
            'total_scores': 0,
            'lgb_only': 0,
            'llm_only': 0,
            'hybrid': 0,
            'fallback': 0
        }

    async def score(
        self,
        title: str,
        text: str,
        publish_time: Optional[datetime],
        metrics: Dict,
        author_id: Optional[str],
        db: Optional[Session],
        use_llm: bool = True
    ) -> Dict:
        """
        评分

        Args:
            title: 标题
            text: 正文
            publish_time: 发布时间
            metrics: 指标
            author_id: 作者ID
            db: 数据库会话
            use_llm: 是否使用LLM

        Returns:
            评分结果
        """
        self.stats['total_scores'] += 1

        result = {
            'lgb_score': None,
            'llm_score': None,
            'final_score': None,
            'confidence': 0.0,
            'method': None,
            'timestamp': datetime.now().isoformat()
        }

        try:
            # 1. 提取特征
            features = self.feature_extractor.extract_all_features(
                title=title,
                text=text,
                publish_time=publish_time,
                metrics=metrics,
                author_id=author_id,
                db=db
            )

            # 2. LightGBM预测
            lgb_score = self.lgb_trainer.predict(features)
            result['lgb_score'] = float(lgb_score)

            # 3. 计算置信度
            confidence = self._calculate_confidence(features, lgb_score)
            result['confidence'] = confidence

            # 4. 决定是否使用LLM
            if use_llm and confidence < self.use_llm_threshold:
                # 置信度低，使用LLM补充
                llm_score = await self._get_llm_score(title, text)
                result['llm_score'] = llm_score

                # 混合评分
                result['final_score'] = (
                    self.lgb_weight * lgb_score +
                    self.llm_weight * llm_score
                )
                result['method'] = 'hybrid'
                self.stats['hybrid'] += 1

            else:
                # 置信度高，仅使用LightGBM
                result['final_score'] = lgb_score
                result['method'] = 'lgb_only'
                self.stats['lgb_only'] += 1

        except Exception as e:
            logger.error(f"评分失败: {e}")

            # 降级：仅使用LLM
            if use_llm:
                try:
                    llm_score = await self._get_llm_score(title, text)
                    result['llm_score'] = llm_score
                    result['final_score'] = llm_score
                    result['method'] = 'llm_fallback'
                    self.stats['fallback'] += 1

                except Exception as e2:
                    logger.error(f"LLM评分也失败: {e2}")
                    result['final_score'] = 0.5  # 默认分数
                    result['method'] = 'default'

            else:
                result['final_score'] = 0.5
                result['method'] = 'default'

        return result

    async def score_batch(
        self,
        items: list,
        use_llm: bool = True
    ) -> list:
        """
        批量评分

        Args:
            items: 待评分项列表
            use_llm: 是否使用LLM

        Returns:
            评分结果列表
        """
        tasks = []
        for item in items:
            task = self.score(
                title=item['title'],
                text=item['text'],
                publish_time=item.get('publish_time'),
                metrics=item.get('metrics', {}),
                author_id=item.get('author_id'),
                db=item.get('db'),
                use_llm=use_llm
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        return results

    def _calculate_confidence(self, features: Dict, score: float) -> float:
        """
        Calculate confidence using prediction variance from LightGBM model + calibration.
        """
        import numpy as np

        # 1. Feature completeness
        n_features = max(len(features), 1)
        feature_completeness = sum(1 for v in features.values() if v != 0) / n_features

        # 2. Model prediction variance (if LightGBM model available)
        model_confidence = 0.5
        try:
            if hasattr(self, 'lgb_trainer') and self.lgb_trainer and hasattr(self.lgb_trainer, 'model') and self.lgb_trainer.model is not None:
                feature_names = sorted(features.keys())
                X = np.array([[features.get(name, 0.0) for name in feature_names]])
                # Use individual tree predictions to estimate variance
                if hasattr(self.lgb_trainer.model, 'predict'):
                    preds = []
                    n_trees = getattr(self.lgb_trainer.model, 'n_estimators_', 100)
                    for i in range(1, min(n_trees + 1, 50), 5):
                        pred = self.lgb_trainer.model.predict(X, num_iteration=i)
                        preds.append(pred[0])
                    if preds:
                        variance = np.var(preds)
                        model_confidence = float(np.clip(1.0 - variance * 10, 0.1, 1.0))
        except Exception:
            pass

        # 3. Score stability (extreme predictions are less confident)
        score_stability = 1.0 - abs(score - 0.5) * 1.5

        # 4. Calibrated confidence
        confidence = 0.4 * feature_completeness + 0.35 * model_confidence + 0.25 * max(score_stability, 0)
        return float(np.clip(confidence, 0.0, 1.0))

    async def _get_llm_score(self, title: str, text: str) -> float:
        """
        Get LLM-based quality score by calling UnifiedLLM with a structured scoring prompt.
        """
        try:
            from app.engine.llm.unified import UnifiedLLM
            llm = UnifiedLLM()

            prompt = f"""Rate the quality of this social media content on a scale of 0.0 to 1.0.

Title: {title[:200]}
Content: {text[:800]}

Evaluate based on:
- Hook effectiveness (does it grab attention?)
- Content value (informative, entertaining, or useful?)
- Structure and readability
- Call-to-action clarity
- Overall engagement potential

Respond with JSON only:
{{"score": 0.0-1.0, "reasoning": "brief explanation"}}"""

            response = await llm.structured_output(
                messages=[{"role": "user", "content": prompt}],
                schema={"score": "number", "reasoning": "string"},
                provider="claude",
                model="haiku-4.5",
                temperature=0.3,
            )
            score = float(response.get("score", 0.5))
            return max(0.0, min(score, 1.0))

        except Exception as e:
            logger.warning(f"LLM scoring failed: {e}, using heuristic fallback")
            # Heuristic fallback
            score = 0.5
            if 10 <= len(title) <= 30:
                score += 0.1
            if 100 <= len(text) <= 1000:
                score += 0.1
            return min(score, 1.0)

    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = self.stats['total_scores']

        if total == 0:
            return self.stats

        return {
            **self.stats,
            'lgb_only_rate': self.stats['lgb_only'] / total,
            'llm_only_rate': self.stats['llm_only'] / total,
            'hybrid_rate': self.stats['hybrid'] / total,
            'fallback_rate': self.stats['fallback'] / total,
            'cost_reduction': self.stats['lgb_only'] / total  # LightGBM节省的成本比例
        }

    def adjust_weights(self, lgb_weight: float, llm_weight: float):
        """
        调整权重

        Args:
            lgb_weight: LightGBM权重
            llm_weight: LLM权重
        """
        total = lgb_weight + llm_weight
        self.lgb_weight = lgb_weight / total
        self.llm_weight = llm_weight / total

        logger.info(f"权重已调整: LGB={self.lgb_weight:.2f}, LLM={self.llm_weight:.2f}")


# ==================== 使用示例 ====================

async def example_usage():
    """使用示例"""
    from app.db import get_db
    from app.ml.lightgbm_trainer import LightGBMTrainer
    from app.ml.feature_extractor import FeatureExtractor

    # 1. 创建组件
    feature_extractor = FeatureExtractor()
    lgb_trainer = LightGBMTrainer()

    # 加载已训练的模型
    lgb_trainer.load_model('viral_predictor')

    # 2. 创建混合评分器
    scorer = HybridScorer(
        lgb_trainer=lgb_trainer,
        feature_extractor=feature_extractor,
        lgb_weight=0.7,
        llm_weight=0.3
    )

    # 3. 单个评分
    result = await scorer.score(
        title="🔥超好用的护肤品推荐",
        text="今天给大家分享几款我最近在用的护肤品...",
        publish_time=datetime.now(),
        metrics={'views': 1000, 'likes': 100, 'comments': 10, 'collects': 50, 'shares': 5},
        author_id=None,
        db=None,
        use_llm=True
    )

    print(f"评分结果: {result}")

    # 4. 批量评分
    items = [
        {
            'title': '标题1',
            'text': '内容1',
            'metrics': {'views': 1000, 'likes': 100, 'comments': 10, 'collects': 50, 'shares': 5}
        },
        {
            'title': '标题2',
            'text': '内容2',
            'metrics': {'views': 2000, 'likes': 200, 'comments': 20, 'collects': 100, 'shares': 10}
        }
    ]

    results = await scorer.score_batch(items, use_llm=True)
    print(f"批量评分结果: {results}")

    # 5. 获取统计
    stats = scorer.get_stats()
    print(f"统计信息: {stats}")
    print(f"成本节省: {stats['cost_reduction']:.2%}")
