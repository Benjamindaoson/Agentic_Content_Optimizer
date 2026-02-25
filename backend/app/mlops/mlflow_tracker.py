"""
MLflow 集成 - 实验追踪和模型管理

提供完整的 MLOps 能力：
1. 实验追踪 - 记录所有生成任务的参数和结果
2. 模型版本管理 - 管理 GRPO 模型的版本
3. 指标记录 - 追踪性能指标和业务指标
4. 模型注册 - 注册和部署最佳模型
"""

from typing import Dict, Any, Optional, List
import mlflow
import mlflow.pyfunc
from mlflow.tracking import MlflowClient
from datetime import datetime
import logging
import json
import os

logger = logging.getLogger(__name__)


class MLflowConfig:
    """MLflow 配置"""
    def __init__(
        self,
        tracking_uri: str = "sqlite:///mlflow.db",
        experiment_name: str = "growth-flywheel",
        artifact_location: Optional[str] = None,
        enable_autolog: bool = True
    ):
        self.tracking_uri = tracking_uri
        self.experiment_name = experiment_name
        self.artifact_location = artifact_location or "./mlruns"
        self.enable_autolog = enable_autolog


class MLflowTracker:
    """
    MLflow 实验追踪器

    核心功能：
    1. 追踪内容生成实验
    2. 记录 GRPO 训练过程
    3. 管理模型版本
    4. 对比实验结果
    """

    def __init__(self, config: Optional[MLflowConfig] = None):
        """初始化 MLflow 追踪器

        Args:
            config: MLflow 配置
        """
        self.config = config or MLflowConfig()

        # 设置 tracking URI
        mlflow.set_tracking_uri(self.config.tracking_uri)

        # 创建或获取实验
        try:
            self.experiment = mlflow.get_experiment_by_name(
                self.config.experiment_name
            )
            if self.experiment is None:
                experiment_id = mlflow.create_experiment(
                    name=self.config.experiment_name,
                    artifact_location=self.config.artifact_location
                )
                self.experiment = mlflow.get_experiment(experiment_id)
        except Exception as e:
            logger.error(f"Failed to create/get experiment: {e}")
            self.experiment = None

        # 创建 MLflow 客户端
        self.client = MlflowClient(tracking_uri=self.config.tracking_uri)

        # 启用自动日志
        if self.config.enable_autolog:
            mlflow.autolog(disable=False)

        logger.info(
            f"MLflow tracker initialized: "
            f"experiment={self.config.experiment_name}, "
            f"tracking_uri={self.config.tracking_uri}"
        )

    def start_run(
        self,
        run_name: str,
        tags: Optional[Dict[str, str]] = None,
        nested: bool = False
    ) -> mlflow.ActiveRun:
        """开始一个新的 MLflow run

        Args:
            run_name: Run 名称
            tags: 标签
            nested: 是否为嵌套 run

        Returns:
            MLflow ActiveRun
        """
        if self.experiment is None:
            logger.warning("No experiment available, creating default")
            experiment_id = mlflow.create_experiment("default")
        else:
            experiment_id = self.experiment.experiment_id

        run = mlflow.start_run(
            experiment_id=experiment_id,
            run_name=run_name,
            tags=tags,
            nested=nested
        )

        logger.info(f"Started MLflow run: {run_name} (id={run.info.run_id})")
        return run

    def log_generation_experiment(
        self,
        generation_id: str,
        topic: str,
        platform: str,
        pattern_id: Optional[str],
        params: Dict[str, Any],
        metrics: Dict[str, float],
        artifacts: Optional[Dict[str, str]] = None
    ) -> str:
        """记录内容生成实验

        Args:
            generation_id: 生成 ID
            topic: 主题
            platform: 平台
            pattern_id: 模式 ID
            params: 生成参数
            metrics: 评估指标
            artifacts: 产物（内容文本等）

        Returns:
            Run ID
        """
        with self.start_run(
            run_name=f"generation_{generation_id[:8]}",
            tags={
                "type": "generation",
                "generation_id": generation_id,
                "platform": platform,
                "pattern_id": pattern_id or "unknown"
            }
        ) as run:
            # 记录参数
            mlflow.log_params({
                "topic": topic,
                "platform": platform,
                "pattern_id": pattern_id,
                **params
            })

            # 记录指标
            mlflow.log_metrics(metrics)

            # 记录产物
            if artifacts:
                for name, content in artifacts.items():
                    # 保存为临时文件
                    temp_file = f"/tmp/{name}_{generation_id}.txt"
                    with open(temp_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    mlflow.log_artifact(temp_file, artifact_path="outputs")
                    os.remove(temp_file)

            logger.info(
                f"Logged generation experiment: {generation_id}, "
                f"metrics={metrics}"
            )

            return run.info.run_id

    def log_grpo_training(
        self,
        run_id: str,
        training_params: Dict[str, Any],
        training_metrics: Dict[str, float],
        pattern_updates: List[Dict[str, Any]]
    ) -> str:
        """记录 GRPO 训练过程

        Args:
            run_id: GRPO run ID
            training_params: 训练参数
            training_metrics: 训练指标
            pattern_updates: 模式更新列表

        Returns:
            MLflow Run ID
        """
        with self.start_run(
            run_name=f"grpo_training_{run_id[:8]}",
            tags={
                "type": "grpo_training",
                "grpo_run_id": run_id
            }
        ) as run:
            # 记录训练参数
            mlflow.log_params(training_params)

            # 记录训练指标
            mlflow.log_metrics(training_metrics)

            # 记录模式更新
            updates_file = f"/tmp/pattern_updates_{run_id}.json"
            with open(updates_file, 'w', encoding='utf-8') as f:
                json.dump(pattern_updates, f, indent=2, ensure_ascii=False)
            mlflow.log_artifact(updates_file, artifact_path="training")
            os.remove(updates_file)

            logger.info(
                f"Logged GRPO training: {run_id}, "
                f"patterns_updated={len(pattern_updates)}"
            )

            return run.info.run_id

    def log_rag_evaluation(
        self,
        query: str,
        retriever_name: str,
        metrics: Dict[str, float],
        retrieved_docs: List[Dict[str, Any]]
    ) -> str:
        """记录 RAG 评估

        Args:
            query: 查询
            retriever_name: 检索器名称
            metrics: 评估指标
            retrieved_docs: 检索到的文档

        Returns:
            Run ID
        """
        with self.start_run(
            run_name=f"rag_eval_{retriever_name}",
            tags={
                "type": "rag_evaluation",
                "retriever": retriever_name
            }
        ) as run:
            # 记录参数
            mlflow.log_params({
                "query": query[:100],  # 截断长查询
                "retriever": retriever_name,
                "num_docs": len(retrieved_docs)
            })

            # 记录指标
            mlflow.log_metrics(metrics)

            # 记录检索结果
            docs_file = f"/tmp/retrieved_docs_{run.info.run_id}.json"
            with open(docs_file, 'w', encoding='utf-8') as f:
                json.dump(retrieved_docs, f, indent=2, ensure_ascii=False)
            mlflow.log_artifact(docs_file, artifact_path="rag")
            os.remove(docs_file)

            return run.info.run_id

    def log_metrics_over_time(
        self,
        metrics: Dict[str, float],
        step: int
    ):
        """记录随时间变化的指标

        Args:
            metrics: 指标字典
            step: 步骤/时间戳
        """
        for key, value in metrics.items():
            mlflow.log_metric(key, value, step=step)

    def register_model(
        self,
        model_name: str,
        run_id: str,
        model_path: str,
        tags: Optional[Dict[str, str]] = None
    ) -> str:
        """注册模型到 MLflow Model Registry

        Args:
            model_name: 模型名称
            run_id: Run ID
            model_path: 模型路径
            tags: 标签

        Returns:
            Model version
        """
        try:
            # 注册模型
            model_uri = f"runs:/{run_id}/{model_path}"
            model_version = mlflow.register_model(
                model_uri=model_uri,
                name=model_name,
                tags=tags
            )

            logger.info(
                f"Registered model: {model_name}, "
                f"version={model_version.version}"
            )

            return model_version.version

        except Exception as e:
            logger.error(f"Failed to register model: {e}")
            return None

    def transition_model_stage(
        self,
        model_name: str,
        version: str,
        stage: str
    ):
        """转换模型阶段

        Args:
            model_name: 模型名称
            version: 版本号
            stage: 阶段 (Staging/Production/Archived)
        """
        try:
            self.client.transition_model_version_stage(
                name=model_name,
                version=version,
                stage=stage
            )

            logger.info(
                f"Transitioned model {model_name} v{version} to {stage}"
            )

        except Exception as e:
            logger.error(f"Failed to transition model stage: {e}")

    def get_best_run(
        self,
        metric_name: str,
        ascending: bool = False,
        filter_string: Optional[str] = None
    ) -> Optional[mlflow.entities.Run]:
        """获取最佳 run

        Args:
            metric_name: 指标名称
            ascending: 是否升序（True 表示越小越好）
            filter_string: 过滤条件

        Returns:
            最佳 Run
        """
        if self.experiment is None:
            return None

        try:
            runs = self.client.search_runs(
                experiment_ids=[self.experiment.experiment_id],
                filter_string=filter_string,
                order_by=[f"metrics.{metric_name} {'ASC' if ascending else 'DESC'}"],
                max_results=1
            )

            if runs:
                best_run = runs[0]
                logger.info(
                    f"Best run: {best_run.info.run_id}, "
                    f"{metric_name}={best_run.data.metrics.get(metric_name)}"
                )
                return best_run

            return None

        except Exception as e:
            logger.error(f"Failed to get best run: {e}")
            return None

    def compare_runs(
        self,
        run_ids: List[str],
        metric_names: List[str]
    ) -> Dict[str, Dict[str, float]]:
        """对比多个 runs

        Args:
            run_ids: Run ID 列表
            metric_names: 指标名称列表

        Returns:
            对比结果
        """
        comparison = {}

        for run_id in run_ids:
            try:
                run = self.client.get_run(run_id)
                comparison[run_id] = {
                    metric: run.data.metrics.get(metric, 0.0)
                    for metric in metric_names
                }
            except Exception as e:
                logger.error(f"Failed to get run {run_id}: {e}")

        return comparison

    def get_experiment_summary(self) -> Dict[str, Any]:
        """获取实验摘要

        Returns:
            实验摘要
        """
        if self.experiment is None:
            return {"status": "no_experiment"}

        try:
            # 获取所有 runs
            runs = self.client.search_runs(
                experiment_ids=[self.experiment.experiment_id],
                max_results=1000
            )

            # 按类型分组
            runs_by_type = {}
            for run in runs:
                run_type = run.data.tags.get("type", "unknown")
                if run_type not in runs_by_type:
                    runs_by_type[run_type] = []
                runs_by_type[run_type].append(run)

            # 统计
            summary = {
                "experiment_name": self.experiment.name,
                "experiment_id": self.experiment.experiment_id,
                "total_runs": len(runs),
                "runs_by_type": {
                    run_type: len(run_list)
                    for run_type, run_list in runs_by_type.items()
                },
                "latest_run": runs[0].info.run_id if runs else None,
                "latest_run_time": runs[0].info.start_time if runs else None
            }

            return summary

        except Exception as e:
            logger.error(f"Failed to get experiment summary: {e}")
            return {"status": "error", "error": str(e)}


# 全局实例（单例）
_mlflow_tracker_instance: Optional[MLflowTracker] = None


def get_mlflow_tracker(config: Optional[MLflowConfig] = None) -> MLflowTracker:
    """获取 MLflow 追踪器实例（单例）

    Args:
        config: MLflow 配置

    Returns:
        MLflowTracker 实例
    """
    global _mlflow_tracker_instance

    if _mlflow_tracker_instance is None:
        _mlflow_tracker_instance = MLflowTracker(config)
        logger.info("Global MLflowTracker instance created")

    return _mlflow_tracker_instance
