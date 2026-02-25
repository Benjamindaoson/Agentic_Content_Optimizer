"""
ML Training System

生产级 LLM 训练系统，支持 QLoRA SFT 和 DPO 训练
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.ml.training.schemas import GenerationTrace, Outcome, TrainingDataset
    from app.ml.models.adapter_registry import AdapterRegistry
    from app.ml.services.training_service import TrainingService


def __getattr__(name: str):
    # 延迟导入，避免启动时把 mlflow / 训练组件全部拉起
    if name in {"GenerationTrace", "Outcome", "TrainingDataset"}:
        from app.ml.training.schemas import GenerationTrace, Outcome, TrainingDataset
        mapping = {
            "GenerationTrace": GenerationTrace,
            "Outcome": Outcome,
            "TrainingDataset": TrainingDataset,
        }
        return mapping[name]
    if name == "AdapterRegistry":
        from app.ml.models.adapter_registry import AdapterRegistry
        return AdapterRegistry
    if name == "TrainingService":
        from app.ml.services.training_service import TrainingService
        return TrainingService
    raise AttributeError(name)

__all__ = [
    "GenerationTrace",
    "Outcome",
    "TrainingDataset",
    "AdapterRegistry",
    "TrainingService",
]
