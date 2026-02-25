"""
真实指标预测器

基于历史数据训练的预测模型，用于预测真实用户行为指标：
- CTR (点击率)
- Completion Rate (完播率)
- Engagement Rate (互动率)
- Conversion Rate (转化率)

使用 LightGBM 进行训练和预测
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
import numpy as np
from pathlib import Path
import pickle
import json
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """特征提取器"""

    def __init__(self):
        self.hook_types = {}
        self.body_types = {}
        self.cta_types = {}

    def extract_features(
        self,
        content: Dict[str, Any],
        action: Optional[Dict[str, Any]] = None
    ) -> Dict[str, float]:
        """
        提取特征

        Args:
            content: 内容数据
            action: 动作数据（可选）

        Returns:
            特征字典
        """
        features = {}

        # 1. 动作特征（如果提供）
        if action:
            hook_id = action.get('hook_id', 0)
            body_id = action.get('body_id', 0)
            cta_id = action.get('cta_id', 0)

            features['hook_id'] = float(hook_id)
            features['body_id'] = float(body_id)
            features['cta_id'] = float(cta_id)

        # 2. 长度特征
        hook_text = content.get('hook', '')
        body_text = content.get('body', '')
        cta_text = content.get('cta', '')

        features['hook_length'] = float(len(hook_text))
        features['body_length'] = float(len(body_text))
        features['cta_length'] = float(len(cta_text))
        features['total_length'] = float(len(hook_text) + len(body_text) + len(cta_text))

        # 3. 结构特征
        full_text = f"{hook_text} {body_text} {cta_text}"
        features['has_numbers'] = float(any(c.isdigit() for c in full_text))
        features['has_question'] = float('?' in full_text or '？' in full_text)
        features['sentence_count'] = float(full_text.count('.') + full_text.count('。') +
                                          full_text.count('!') + full_text.count('！'))

        # 4. 关键词特征
        keywords = ['限时', '免费', '独家', '新品', '折扣', '优惠', '立即', '马上']
        features['keyword_count'] = float(sum(1 for kw in keywords if kw in full_text))

        # 5. 情感特征（简单版本）
        positive_words = ['好', '棒', '赞', '优秀', '完美', '喜欢', '爱']
        negative_words = ['差', '烂', '糟', '失望', '不好']
        features['positive_count'] = float(sum(1 for w in positive_words if w in full_text))
        features['negative_count'] = float(sum(1 for w in negative_words if w in full_text))

        return features

    def extract_batch_features(
        self,
        contents: List[Dict[str, Any]],
        actions: Optional[List[Dict[str, Any]]] = None
    ) -> np.ndarray:
        """
        批量提取特征

        Args:
            contents: 内容列表
            actions: 动作列表（可选）

        Returns:
            特征矩阵 (n_samples, n_features)
        """
        if actions is None:
            actions = [None] * len(contents)

        feature_dicts = [
            self.extract_features(content, action)
            for content, action in zip(contents, actions)
        ]

        # 转换为矩阵
        if not feature_dicts:
            return np.array([])

        feature_names = sorted(feature_dicts[0].keys())
        feature_matrix = np.array([
            [fd.get(name, 0.0) for name in feature_names]
            for fd in feature_dicts
        ])

        return feature_matrix


class BaseMetricPredictor:
    """基础指标预测器"""

    def __init__(self, metric_name: str):
        self.metric_name = metric_name
        self.model = None
        self.feature_extractor = FeatureExtractor()
        self.scaler = StandardScaler()  # Feature scaling
        self.is_trained = False

    def train(
        self,
        contents: List[Dict[str, Any]],
        actions: List[Dict[str, Any]],
        labels: List[float],
        **kwargs
    ):
        """
        训练模型

        Args:
            contents: 内容列表
            actions: 动作列表
            labels: 标签列表
            **kwargs: 额外参数
        """
        try:
            import lightgbm as lgb
            from sklearn.model_selection import train_test_split
        except ImportError:
            logger.warning("LightGBM 未安装，使用简单线性模型")
            self._train_simple_model(contents, actions, labels)
            return

        # 提取特征
        X = self.feature_extractor.extract_batch_features(contents, actions)
        y = np.array(labels)

        # Feature scaling
        X_scaled = self.scaler.fit_transform(X)

        # Train/validation/test split (70/15/15)
        X_train, X_temp, y_train, y_temp = train_test_split(
            X_scaled, y, test_size=0.3, random_state=42
        )
        X_val, X_test, y_val, y_test = train_test_split(
            X_temp, y_temp, test_size=0.5, random_state=42
        )

        # 训练 LightGBM
        self.model = lgb.LGBMRegressor(
            n_estimators=kwargs.get('n_estimators', 100),
            learning_rate=kwargs.get('learning_rate', 0.05),
            max_depth=kwargs.get('max_depth', 6),
            random_state=42
        )

        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            eval_metric='rmse',
            callbacks=[lgb.early_stopping(stopping_rounds=10, verbose=False)]
        )
        self.is_trained = True

        # Evaluate on test set
        test_predictions = self.model.predict(X_test)
        test_rmse = np.sqrt(np.mean((test_predictions - y_test) ** 2))

        logger.info(f"✅ {self.metric_name} 预测器训练完成")
        logger.info(f"   训练集: {len(X_train)} 样本")
        logger.info(f"   验证集: {len(X_val)} 样本")
        logger.info(f"   测试集: {len(X_test)} 样本, RMSE: {test_rmse:.4f}")

    def _train_simple_model(
        self,
        contents: List[Dict[str, Any]],
        actions: List[Dict[str, Any]],
        labels: List[float]
    ):
        """Train fallback model using sklearn GradientBoostingRegressor."""
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.model_selection import train_test_split

        X = self.feature_extractor.extract_batch_features(contents, actions)
        y = np.array(labels)

        if len(X) < 5:
            self.model = {'type': 'mean', 'value': float(np.mean(labels))}
            self.is_trained = True
            logger.info(f"{self.metric_name} too few samples, using mean predictor")
            return

        X_scaled = self.scaler.fit_transform(X)
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.2, random_state=42
        )

        self.model = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.05,
            max_depth=4,
            random_state=42,
        )
        self.model.fit(X_train, y_train)
        self.is_trained = True

        test_rmse = np.sqrt(np.mean((self.model.predict(X_test) - y_test) ** 2))
        logger.info(
            f"{self.metric_name} GBR predictor trained: "
            f"{len(X_train)} train, {len(X_test)} test, RMSE={test_rmse:.4f}"
        )

    def predict(
        self,
        content: Dict[str, Any],
        action: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        预测单个样本

        Args:
            content: 内容数据
            action: 动作数据

        Returns:
            预测值
        """
        if not self.is_trained:
            logger.warning(f"{self.metric_name} 预测器未训练，返回默认值")
            return 0.5

        if isinstance(self.model, dict) and self.model.get('type') == 'mean':
            return self.model['value']

        try:
            features = self.feature_extractor.extract_features(content, action)
            feature_names = sorted(features.keys())
            X = np.array([[features[name] for name in feature_names]])
            X_scaled = self.scaler.transform(X)
            prediction = self.model.predict(X_scaled)[0]
            return float(np.clip(prediction, 0.0, 1.0))
        except Exception as e:
            logger.warning(f"{self.metric_name} prediction failed: {e}, returning default")
            return 0.5

    def predict_batch(
        self,
        contents: List[Dict[str, Any]],
        actions: Optional[List[Dict[str, Any]]] = None
    ) -> List[float]:
        """
        批量预测

        Args:
            contents: 内容列表
            actions: 动作列表

        Returns:
            预测值列表
        """
        if not self.is_trained:
            logger.warning(f"{self.metric_name} 预测器未训练，返回默认值")
            return [0.5] * len(contents)

        if isinstance(self.model, dict) and self.model.get('type') == 'mean':
            return [self.model['value']] * len(contents)

        X = self.feature_extractor.extract_batch_features(contents, actions)

        # Feature scaling
        X_scaled = self.scaler.transform(X)

        predictions = self.model.predict(X_scaled)
        return [float(np.clip(p, 0.0, 1.0)) for p in predictions]

    def save(self, path: str):
        """保存模型"""
        model_data = {
            'metric_name': self.metric_name,
            'model': self.model,
            'scaler': self.scaler,  # Save scaler
            'is_trained': self.is_trained
        }

        with open(path, 'wb') as f:
            pickle.dump(model_data, f)

        logger.info(f"✅ {self.metric_name} 预测器已保存到 {path}")

    def load(self, path: str):
        """加载模型"""
        with open(path, 'rb') as f:
            model_data = pickle.load(f)

        self.metric_name = model_data['metric_name']
        self.model = model_data['model']
        self.scaler = model_data.get('scaler', StandardScaler())  # Load scaler with fallback
        self.is_trained = model_data['is_trained']

        logger.info(f"✅ {self.metric_name} 预测器已从 {path} 加载")


class CTRPredictor(BaseMetricPredictor):
    """CTR（点击率）预测器"""

    def __init__(self):
        super().__init__("CTR")


class CompletionRatePredictor(BaseMetricPredictor):
    """完播率预测器"""

    def __init__(self):
        super().__init__("Completion Rate")


class EngagementRatePredictor(BaseMetricPredictor):
    """互动率预测器"""

    def __init__(self):
        super().__init__("Engagement Rate")


class ConversionRatePredictor(BaseMetricPredictor):
    """转化率预测器"""

    def __init__(self):
        super().__init__("Conversion Rate")


class RealMetricPredictorEnsemble:
    """
    真实指标预测器集成

    管理所有预测器，提供统一接口
    """

    def __init__(self, model_dir: Optional[str] = None):
        self.ctr_predictor = CTRPredictor()
        self.completion_predictor = CompletionRatePredictor()
        self.engagement_predictor = EngagementRatePredictor()
        self.conversion_predictor = ConversionRatePredictor()

        self.model_dir = model_dir
        if model_dir:
            self._load_models()

    def _load_models(self):
        """加载所有模型"""
        model_dir = Path(self.model_dir)
        if not model_dir.exists():
            logger.warning(f"模型目录不存在: {model_dir}")
            return

        try:
            self.ctr_predictor.load(str(model_dir / "ctr_predictor.pkl"))
            self.completion_predictor.load(str(model_dir / "completion_predictor.pkl"))
            self.engagement_predictor.load(str(model_dir / "engagement_predictor.pkl"))
            self.conversion_predictor.load(str(model_dir / "conversion_predictor.pkl"))
            logger.info("✅ 所有预测器加载完成")
        except Exception as e:
            logger.error(f"加载预测器失败: {e}")

    def predict_all(
        self,
        content: Dict[str, Any],
        action: Optional[Dict[str, Any]] = None
    ) -> Dict[str, float]:
        """
        预测所有指标

        Args:
            content: 内容数据
            action: 动作数据

        Returns:
            所有指标的预测值
        """
        return {
            'ctr': self.ctr_predictor.predict(content, action),
            'completion_rate': self.completion_predictor.predict(content, action),
            'engagement_rate': self.engagement_predictor.predict(content, action),
            'conversion_rate': self.conversion_predictor.predict(content, action)
        }

    def train_all(
        self,
        contents: List[Dict[str, Any]],
        actions: List[Dict[str, Any]],
        labels: Dict[str, List[float]],
        **kwargs
    ):
        """
        训练所有预测器

        Args:
            contents: 内容列表
            actions: 动作列表
            labels: 标签字典 {'ctr': [...], 'completion_rate': [...], ...}
            **kwargs: 训练参数
        """
        self.ctr_predictor.train(contents, actions, labels['ctr'], **kwargs)
        self.completion_predictor.train(contents, actions, labels['completion_rate'], **kwargs)
        self.engagement_predictor.train(contents, actions, labels['engagement_rate'], **kwargs)
        self.conversion_predictor.train(contents, actions, labels['conversion_rate'], **kwargs)

        logger.info("✅ 所有预测器训练完成")

    def save_all(self, model_dir: str):
        """保存所有模型"""
        model_path = Path(model_dir)
        model_path.mkdir(parents=True, exist_ok=True)

        self.ctr_predictor.save(str(model_path / "ctr_predictor.pkl"))
        self.completion_predictor.save(str(model_path / "completion_predictor.pkl"))
        self.engagement_predictor.save(str(model_path / "engagement_predictor.pkl"))
        self.conversion_predictor.save(str(model_path / "conversion_predictor.pkl"))

        logger.info(f"✅ 所有预测器已保存到 {model_dir}")
