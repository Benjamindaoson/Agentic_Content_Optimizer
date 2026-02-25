"""
模型管理器 - 管理微调模型的生命周期

核心功能：
1. 模型版本管理
2. 模型加载和卸载
3. 模型部署和回滚
4. 模型性能追踪
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json
import shutil
import logging

logger = logging.getLogger(__name__)


@dataclass
class ModelVersion:
    """模型版本信息"""
    version_id: str
    model_path: str
    base_model: str
    training_method: str  # "dpo", "lora", "sft"
    created_at: datetime
    metrics: Dict[str, float]
    metadata: Dict[str, Any]
    is_active: bool = False


class ModelManager:
    """
    模型管理器

    管理微调模型的完整生命周期
    """

    def __init__(self, models_dir: str = "./models"):
        """初始化模型管理器

        Args:
            models_dir: 模型存储目录
        """
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self.registry_file = self.models_dir / "registry.json"
        self.versions: Dict[str, ModelVersion] = {}

        # 加载注册表
        self._load_registry()

        logger.info(f"ModelManager initialized with {len(self.versions)} versions")

    def _load_registry(self):
        """加载模型注册表"""
        if self.registry_file.exists():
            with open(self.registry_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

                for version_data in data.get("versions", []):
                    version = ModelVersion(
                        version_id=version_data["version_id"],
                        model_path=version_data["model_path"],
                        base_model=version_data["base_model"],
                        training_method=version_data["training_method"],
                        created_at=datetime.fromisoformat(version_data["created_at"]),
                        metrics=version_data.get("metrics", {}),
                        metadata=version_data.get("metadata", {}),
                        is_active=version_data.get("is_active", False)
                    )
                    self.versions[version.version_id] = version

            logger.info(f"Loaded {len(self.versions)} model versions from registry")

    def _save_registry(self):
        """保存模型注册表"""
        data = {
            "versions": [
                {
                    "version_id": v.version_id,
                    "model_path": v.model_path,
                    "base_model": v.base_model,
                    "training_method": v.training_method,
                    "created_at": v.created_at.isoformat(),
                    "metrics": v.metrics,
                    "metadata": v.metadata,
                    "is_active": v.is_active
                }
                for v in self.versions.values()
            ]
        }

        with open(self.registry_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info("Model registry saved")

    def register_model(
        self,
        model_path: str,
        base_model: str,
        training_method: str,
        metrics: Optional[Dict[str, float]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """注册新模型版本

        Args:
            model_path: 模型路径
            base_model: 基础模型名称
            training_method: 训练方法
            metrics: 性能指标
            metadata: 元数据

        Returns:
            版本 ID
        """
        # 生成版本 ID
        version_id = f"v{len(self.versions) + 1}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 创建版本信息
        version = ModelVersion(
            version_id=version_id,
            model_path=model_path,
            base_model=base_model,
            training_method=training_method,
            created_at=datetime.now(),
            metrics=metrics or {},
            metadata=metadata or {},
            is_active=False
        )

        self.versions[version_id] = version
        self._save_registry()

        logger.info(f"Registered model version: {version_id}")

        return version_id

    def get_version(self, version_id: str) -> Optional[ModelVersion]:
        """获取模型版本

        Args:
            version_id: 版本 ID

        Returns:
            模型版本信息
        """
        return self.versions.get(version_id)

    def get_active_version(self) -> Optional[ModelVersion]:
        """获取当前激活的模型版本

        Returns:
            激活的模型版本
        """
        for version in self.versions.values():
            if version.is_active:
                return version
        return None

    def activate_version(self, version_id: str):
        """激活模型版本

        Args:
            version_id: 版本 ID
        """
        if version_id not in self.versions:
            raise ValueError(f"Version {version_id} not found")

        # 取消所有版本的激活状态
        for version in self.versions.values():
            version.is_active = False

        # 激活指定版本
        self.versions[version_id].is_active = True
        self._save_registry()

        logger.info(f"Activated model version: {version_id}")

    def deactivate_all(self):
        """取消所有版本的激活状态"""
        for version in self.versions.values():
            version.is_active = False
        self._save_registry()

        logger.info("Deactivated all model versions")

    def list_versions(
        self,
        training_method: Optional[str] = None,
        limit: int = 10
    ) -> List[ModelVersion]:
        """列出模型版本

        Args:
            training_method: 过滤训练方法
            limit: 返回数量限制

        Returns:
            模型版本列表
        """
        versions = list(self.versions.values())

        # 过滤
        if training_method:
            versions = [v for v in versions if v.training_method == training_method]

        # 按创建时间排序
        versions.sort(key=lambda v: v.created_at, reverse=True)

        return versions[:limit]

    def compare_versions(
        self,
        version_id1: str,
        version_id2: str
    ) -> Dict[str, Any]:
        """比较两个模型版本

        Args:
            version_id1: 版本 1 ID
            version_id2: 版本 2 ID

        Returns:
            比较结果
        """
        v1 = self.get_version(version_id1)
        v2 = self.get_version(version_id2)

        if not v1 or not v2:
            raise ValueError("One or both versions not found")

        # 比较指标
        metric_comparison = {}
        all_metrics = set(v1.metrics.keys()) | set(v2.metrics.keys())

        for metric in all_metrics:
            m1 = v1.metrics.get(metric, 0)
            m2 = v2.metrics.get(metric, 0)
            metric_comparison[metric] = {
                "v1": m1,
                "v2": m2,
                "diff": m2 - m1,
                "improvement": ((m2 - m1) / m1 * 100) if m1 != 0 else 0
            }

        return {
            "version1": {
                "id": v1.version_id,
                "created_at": v1.created_at.isoformat(),
                "training_method": v1.training_method
            },
            "version2": {
                "id": v2.version_id,
                "created_at": v2.created_at.isoformat(),
                "training_method": v2.training_method
            },
            "metrics": metric_comparison
        }

    def delete_version(self, version_id: str, delete_files: bool = False):
        """删除模型版本

        Args:
            version_id: 版本 ID
            delete_files: 是否删除模型文件
        """
        if version_id not in self.versions:
            raise ValueError(f"Version {version_id} not found")

        version = self.versions[version_id]

        # 不能删除激活的版本
        if version.is_active:
            raise ValueError("Cannot delete active version")

        # 删除文件
        if delete_files:
            model_path = Path(version.model_path)
            if model_path.exists():
                shutil.rmtree(model_path)
                logger.info(f"Deleted model files: {model_path}")

        # 从注册表删除
        del self.versions[version_id]
        self._save_registry()

        logger.info(f"Deleted model version: {version_id}")

    def get_best_version(self, metric: str = "overall_score") -> Optional[ModelVersion]:
        """获取最佳模型版本

        Args:
            metric: 评估指标

        Returns:
            最佳模型版本
        """
        versions_with_metric = [
            v for v in self.versions.values()
            if metric in v.metrics
        ]

        if not versions_with_metric:
            return None

        best_version = max(
            versions_with_metric,
            key=lambda v: v.metrics[metric]
        )

        return best_version

    def update_metrics(
        self,
        version_id: str,
        metrics: Dict[str, float]
    ):
        """更新模型版本的指标

        Args:
            version_id: 版本 ID
            metrics: 新指标
        """
        if version_id not in self.versions:
            raise ValueError(f"Version {version_id} not found")

        self.versions[version_id].metrics.update(metrics)
        self._save_registry()

        logger.info(f"Updated metrics for version {version_id}")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息

        Returns:
            统计信息
        """
        active_version = self.get_active_version()

        return {
            "total_versions": len(self.versions),
            "active_version": active_version.version_id if active_version else None,
            "training_methods": {
                method: len([v for v in self.versions.values() if v.training_method == method])
                for method in set(v.training_method for v in self.versions.values())
            },
            "latest_version": max(
                self.versions.values(),
                key=lambda v: v.created_at
            ).version_id if self.versions else None
        }
