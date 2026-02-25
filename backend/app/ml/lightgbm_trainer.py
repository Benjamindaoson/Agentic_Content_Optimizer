"""
LightGBM 训练器

用于训练预测模型，替代LLM评分
"""

import logging
import pickle
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from sqlalchemy.orm import Session
from app.db import XHSNote, XHSMetrics, XHSAnalysis
from app.ml.feature_extractor import FeatureExtractor

logger = logging.getLogger(__name__)


class LightGBMTrainer:
    """
    LightGBM 训练器

    功能：
    1. 训练爆款预测模型
    2. 替代LLM评分
    3. 模型持久化
    4. 模型评估
    """

    def __init__(
        self,
        model_dir: str = './models',
        feature_extractor: Optional[FeatureExtractor] = None
    ):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self.feature_extractor = feature_extractor or FeatureExtractor()

        # 模型
        self.model = None
        self.feature_names = None

        # 训练历史
        self.training_history = []

    def prepare_training_data(
        self,
        db: Session,
        min_samples: int = 100,
        category: Optional[str] = None
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        准备训练数据

        Args:
            db: 数据库会话
            min_samples: 最小样本数
            category: 分类过滤

        Returns:
            (特征DataFrame, 标签Series)
        """
        logger.info("开始准备训练数据")

        # 1. 查询笔记数据
        query = db.query(XHSNote).join(XHSMetrics).join(XHSAnalysis)

        if category:
            query = query.filter(XHSNote.category == category)

        notes = query.limit(min_samples * 10).all()  # 多查询一些，防止数据不足

        logger.info(f"查询到 {len(notes)} 条笔记")

        # 2. 提取特征
        features_list = []
        labels = []

        for note in notes:
            try:
                # 获取指标
                metrics = db.query(XHSMetrics).filter(
                    XHSMetrics.note_id == note.note_id
                ).first()

                # 获取分析结果
                analysis = db.query(XHSAnalysis).filter(
                    XHSAnalysis.note_id == note.note_id
                ).first()

                if not metrics or not analysis or analysis.overall_score is None:
                    continue

                # 提取特征
                metrics_dict = {
                    'views': metrics.views,
                    'likes': metrics.likes,
                    'comments': metrics.comments,
                    'collects': metrics.collects,
                    'shares': metrics.shares
                }

                features = self.feature_extractor.extract_all_features(
                    title=note.title,
                    text=note.text,
                    publish_time=note.publish_time,
                    metrics=metrics_dict,
                    author_id=note.author_id,
                    db=db
                )

                features_list.append(features)
                labels.append(analysis.overall_score)

            except Exception as e:
                logger.error(f"提取特征失败: {note.note_id}, error={e}")
                continue

        if len(features_list) < min_samples:
            raise ValueError(f"样本不足: {len(features_list)}/{min_samples}")

        # 3. 转换为DataFrame
        X = pd.DataFrame(features_list)
        y = pd.Series(labels)

        # 保存特征名称
        self.feature_names = X.columns.tolist()

        logger.info(f"✅ 准备完成: {len(X)} 个样本, {len(X.columns)} 个特征")

        return X, y

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        params: Optional[Dict] = None,
        test_size: float = 0.2
    ) -> Dict:
        """
        训练模型

        Args:
            X: 特征
            y: 标签
            params: LightGBM参数
            test_size: 测试集比例

        Returns:
            训练结果
        """
        logger.info("开始训练模型")

        # 1. 划分训练集和测试集
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )

        # 2. 默认参数
        if params is None:
            params = {
                'objective': 'regression',
                'metric': 'rmse',
                'boosting_type': 'gbdt',
                'num_leaves': 31,
                'learning_rate': 0.05,
                'feature_fraction': 0.9,
                'bagging_fraction': 0.8,
                'bagging_freq': 5,
                'verbose': -1
            }

        # 3. 创建数据集
        train_data = lgb.Dataset(X_train, label=y_train)
        test_data = lgb.Dataset(X_test, label=y_test, reference=train_data)

        # 4. 训练
        evals_result = {}
        self.model = lgb.train(
            params,
            train_data,
            num_boost_round=1000,
            valid_sets=[train_data, test_data],
            valid_names=['train', 'test'],
            callbacks=[
                lgb.early_stopping(stopping_rounds=50),
                lgb.log_evaluation(period=100)
            ],
            evals_result=evals_result
        )

        # 5. 评估
        y_pred_train = self.model.predict(X_train)
        y_pred_test = self.model.predict(X_test)

        train_metrics = {
            'rmse': np.sqrt(mean_squared_error(y_train, y_pred_train)),
            'mae': mean_absolute_error(y_train, y_pred_train),
            'r2': r2_score(y_train, y_pred_train)
        }

        test_metrics = {
            'rmse': np.sqrt(mean_squared_error(y_test, y_pred_test)),
            'mae': mean_absolute_error(y_test, y_pred_test),
            'r2': r2_score(y_test, y_pred_test)
        }

        # 6. 特征重要性
        feature_importance = dict(zip(
            self.feature_names,
            self.model.feature_importance().tolist()
        ))

        # 排序
        feature_importance = dict(
            sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
        )

        result = {
            'train_metrics': train_metrics,
            'test_metrics': test_metrics,
            'feature_importance': feature_importance,
            'num_features': len(self.feature_names),
            'num_samples': len(X),
            'timestamp': datetime.now().isoformat()
        }

        # 记录训练历史
        self.training_history.append(result)

        logger.info(f"✅ 训练完成: Test RMSE={test_metrics['rmse']:.4f}, R2={test_metrics['r2']:.4f}")

        return result

    def predict(self, features: Dict) -> float:
        """
        预测单个样本

        Args:
            features: 特征字典

        Returns:
            预测分数
        """
        if self.model is None:
            raise ValueError("模型未训练")

        # 转换为DataFrame
        X = pd.DataFrame([features])

        # 确保特征顺序一致
        X = X[self.feature_names]

        # 预测
        score = self.model.predict(X)[0]

        return float(score)

    def predict_batch(self, features_list: List[Dict]) -> List[float]:
        """
        批量预测

        Args:
            features_list: 特征字典列表

        Returns:
            预测分数列表
        """
        if self.model is None:
            raise ValueError("模型未训练")

        # 转换为DataFrame
        X = pd.DataFrame(features_list)

        # 确保特征顺序一致
        X = X[self.feature_names]

        # 预测
        scores = self.model.predict(X)

        return scores.tolist()

    def save_model(self, model_name: str = 'viral_predictor'):
        """
        保存模型

        Args:
            model_name: 模型名称
        """
        if self.model is None:
            raise ValueError("模型未训练")

        # 保存模型
        model_path = self.model_dir / f'{model_name}.txt'
        self.model.save_model(str(model_path))

        # 保存特征名称
        feature_path = self.model_dir / f'{model_name}_features.pkl'
        with open(feature_path, 'wb') as f:
            pickle.dump(self.feature_names, f)

        # 保存训练历史
        history_path = self.model_dir / f'{model_name}_history.pkl'
        with open(history_path, 'wb') as f:
            pickle.dump(self.training_history, f)

        logger.info(f"✅ 模型已保存: {model_path}")

    def load_model(self, model_name: str = 'viral_predictor'):
        """
        加载模型

        Args:
            model_name: 模型名称
        """
        # 加载模型
        model_path = self.model_dir / f'{model_name}.txt'
        if not model_path.exists():
            raise FileNotFoundError(f"模型不存在: {model_path}")

        self.model = lgb.Booster(model_file=str(model_path))

        # 加载特征名称
        feature_path = self.model_dir / f'{model_name}_features.pkl'
        with open(feature_path, 'rb') as f:
            self.feature_names = pickle.load(f)

        # 加载训练历史
        history_path = self.model_dir / f'{model_name}_history.pkl'
        if history_path.exists():
            with open(history_path, 'rb') as f:
                self.training_history = pickle.load(f)

        logger.info(f"✅ 模型已加载: {model_path}")

    def retrain(
        self,
        db: Session,
        min_samples: int = 100,
        category: Optional[str] = None
    ) -> Dict:
        """
        重新训练模型

        Args:
            db: 数据库会话
            min_samples: 最小样本数
            category: 分类过滤

        Returns:
            训练结果
        """
        logger.info("开始重新训练模型")

        # 1. 准备数据
        X, y = self.prepare_training_data(db, min_samples, category)

        # 2. 训练
        result = self.train(X, y)

        # 3. 保存
        self.save_model()

        logger.info("✅ 重新训练完成")

        return result

    def evaluate_vs_llm(
        self,
        db: Session,
        sample_size: int = 100
    ) -> Dict:
        """
        评估模型 vs LLM

        Args:
            db: 数据库会话
            sample_size: 样本数量

        Returns:
            对比结果
        """
        logger.info("开始评估模型 vs LLM")

        # 1. 获取样本
        notes = db.query(XHSNote).join(XHSMetrics).join(XHSAnalysis).limit(sample_size).all()

        lgb_predictions = []
        llm_scores = []

        for note in notes:
            try:
                # 获取指标
                metrics = db.query(XHSMetrics).filter(
                    XHSMetrics.note_id == note.note_id
                ).first()

                # 获取LLM评分
                analysis = db.query(XHSAnalysis).filter(
                    XHSAnalysis.note_id == note.note_id
                ).first()

                if not metrics or not analysis or analysis.overall_score is None:
                    continue

                # 提取特征
                metrics_dict = {
                    'views': metrics.views,
                    'likes': metrics.likes,
                    'comments': metrics.comments,
                    'collects': metrics.collects,
                    'shares': metrics.shares
                }

                features = self.feature_extractor.extract_all_features(
                    title=note.title,
                    text=note.text,
                    publish_time=note.publish_time,
                    metrics=metrics_dict,
                    author_id=note.author_id,
                    db=db
                )

                # LightGBM预测
                lgb_score = self.predict(features)

                lgb_predictions.append(lgb_score)
                llm_scores.append(analysis.overall_score)

            except Exception as e:
                logger.error(f"评估失败: {note.note_id}, error={e}")
                continue

        # 2. 计算指标
        lgb_predictions = np.array(lgb_predictions)
        llm_scores = np.array(llm_scores)

        result = {
            'sample_size': len(lgb_predictions),
            'correlation': np.corrcoef(lgb_predictions, llm_scores)[0, 1],
            'rmse': np.sqrt(mean_squared_error(llm_scores, lgb_predictions)),
            'mae': mean_absolute_error(llm_scores, lgb_predictions),
            'lgb_mean': float(np.mean(lgb_predictions)),
            'llm_mean': float(np.mean(llm_scores)),
            'lgb_std': float(np.std(lgb_predictions)),
            'llm_std': float(np.std(llm_scores))
        }

        logger.info(f"✅ 评估完成: 相关性={result['correlation']:.4f}, RMSE={result['rmse']:.4f}")

        return result


# ==================== 使用示例 ====================

async def example_usage():
    """使用示例"""
    from app.db import get_db

    db = next(get_db())

    # 1. 创建训练器
    trainer = LightGBMTrainer(model_dir='./models')

    # 2. 准备数据
    X, y = trainer.prepare_training_data(db, min_samples=100)

    # 3. 训练模型
    result = trainer.train(X, y)
    print(f"训练结果: {result}")

    # 4. 保存模型
    trainer.save_model('viral_predictor')

    # 5. 加载模型
    trainer.load_model('viral_predictor')

    # 6. 预测
    features = trainer.feature_extractor.extract_all_features(
        title="测试标题",
        text="测试内容",
        publish_time=datetime.now(),
        metrics={'views': 1000, 'likes': 100, 'comments': 10, 'collects': 50, 'shares': 5},
        author_id=None,
        db=None
    )

    score = trainer.predict(features)
    print(f"预测分数: {score:.4f}")

    # 7. 评估 vs LLM
    comparison = trainer.evaluate_vs_llm(db, sample_size=100)
    print(f"对比结果: {comparison}")

    # 8. 重新训练
    retrain_result = trainer.retrain(db, min_samples=200)
    print(f"重新训练结果: {retrain_result}")
