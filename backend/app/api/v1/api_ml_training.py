"""
ML Training API

FastAPI 端点用于训练管理
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import logging

from app.core.database import get_db
from app.ml.services.training_service import TrainingService
from app.ml.models.adapter_registry import AdapterRegistry
from app.ml.models.adapter_loader import AdapterLoader
from app.ml.eval.evaluator import Evaluator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ml", tags=["ml"])


# ==================== Request/Response Models ====================

class SFTTrainingRequest(BaseModel):
    """SFT 训练请求"""
    platform: str = Field(..., description="平台")
    adapter_name: str = Field(..., description="Adapter 名称")
    base_model: str = Field(default="Qwen/Qwen2.5-7B-Instruct", description="基础模型")
    persona: Optional[str] = Field(default=None, description="人设")
    niche: Optional[str] = Field(default=None, description="领域")
    days: int = Field(default=30, description="数据天数")
    min_engagement_score: float = Field(default=0.01, description="最小互动分")
    max_samples: Optional[int] = Field(default=None, description="最大样本数")
    num_train_epochs: int = Field(default=3, description="训练轮数")
    per_device_train_batch_size: int = Field(default=4, description="批次大小")
    learning_rate: float = Field(default=2e-4, description="学习率")
    eval_split: float = Field(default=0.1, description="验证集比例")


class DPOTrainingRequest(BaseModel):
    """DPO 训练请求"""
    platform: str = Field(..., description="平台")
    adapter_name: str = Field(..., description="Adapter 名称")
    base_adapter: str = Field(..., description="基础 SFT adapter")
    persona: Optional[str] = Field(default=None, description="人设")
    niche: Optional[str] = Field(default=None, description="领域")
    days: int = Field(default=30, description="数据天数")
    min_score_diff: float = Field(default=0.02, description="最小分数差")
    max_pairs: Optional[int] = Field(default=None, description="最大偏好对数")
    num_train_epochs: int = Field(default=1, description="训练轮数")
    per_device_train_batch_size: int = Field(default=2, description="批次大小")
    learning_rate: float = Field(default=5e-5, description="学习率")
    beta: float = Field(default=0.1, description="DPO beta")
    eval_split: float = Field(default=0.1, description="验证集比例")


class AutoTrainingRequest(BaseModel):
    """自动训练请求"""
    platform: str = Field(..., description="平台")
    persona: str = Field(..., description="人设")
    niche: str = Field(..., description="领域")
    sft_days: int = Field(default=30, description="SFT 数据天数")
    dpo_days: int = Field(default=30, description="DPO 数据天数")


class GenerateRequest(BaseModel):
    """生成请求"""
    prompt: str = Field(..., description="输入 prompt")
    adapter_name: Optional[str] = Field(default=None, description="Adapter 名称")
    platform: Optional[str] = Field(default=None, description="平台")
    persona: Optional[str] = Field(default=None, description="人设")
    niche: Optional[str] = Field(default=None, description="领域")
    max_new_tokens: int = Field(default=512, description="最大生成长度")
    temperature: float = Field(default=0.7, description="温度")


class EvaluateRequest(BaseModel):
    """评估请求"""
    adapter_name: str = Field(..., description="Adapter 名称")
    platform: Optional[str] = Field(default=None, description="平台")
    max_samples: int = Field(default=100, description="最大样本数")


# ==================== Training Endpoints ====================

@router.post("/train/sft", status_code=status.HTTP_202_ACCEPTED)
async def train_sft(
    request: SFTTrainingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """训练 SFT adapter（后台任务）"""
    logger.info(f"收到 SFT 训练请求: {request.adapter_name}")

    def _train():
        service = TrainingService(db)
        try:
            result = service.train_sft(**request.model_dump())
            logger.info(f"SFT 训练完成: {result}")
        except Exception as e:
            logger.error(f"SFT 训练失败: {e}", exc_info=True)

    background_tasks.add_task(_train)

    return {
        "status": "accepted",
        "message": f"SFT 训练任务已提交: {request.adapter_name}",
        "adapter_name": request.adapter_name,
    }


@router.post("/train/dpo", status_code=status.HTTP_202_ACCEPTED)
async def train_dpo(
    request: DPOTrainingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """训练 DPO adapter（后台任务）"""
    logger.info(f"收到 DPO 训练请求: {request.adapter_name}")

    def _train():
        service = TrainingService(db)
        try:
            result = service.train_dpo(**request.model_dump())
            logger.info(f"DPO 训练完成: {result}")
        except Exception as e:
            logger.error(f"DPO 训练失败: {e}", exc_info=True)

    background_tasks.add_task(_train)

    return {
        "status": "accepted",
        "message": f"DPO 训练任务已提交: {request.adapter_name}",
        "adapter_name": request.adapter_name,
    }


@router.post("/train/auto", status_code=status.HTTP_202_ACCEPTED)
async def auto_train(
    request: AutoTrainingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """自动训练流水线：SFT -> DPO（后台任务）"""
    logger.info(f"收到自动训练请求: {request.platform}/{request.persona}/{request.niche}")

    def _train():
        service = TrainingService(db)
        try:
            result = service.auto_train_pipeline(**request.model_dump())
            logger.info(f"自动训练完成: {result}")
        except Exception as e:
            logger.error(f"自动训练失败: {e}", exc_info=True)

    background_tasks.add_task(_train)

    return {
        "status": "accepted",
        "message": f"自动训练任务已提交: {request.platform}/{request.persona}/{request.niche}",
    }


# ==================== Adapter Management Endpoints ====================

@router.get("/adapters")
async def list_adapters(
    adapter_type: Optional[str] = None,
    platform: Optional[str] = None,
    persona: Optional[str] = None,
    niche: Optional[str] = None,
    status: str = "active",
    db: Session = Depends(get_db)
):
    """列出所有 adapters"""
    registry = AdapterRegistry(db)
    adapters = registry.list(
        adapter_type=adapter_type,
        platform=platform,
        persona=persona,
        niche=niche,
        status=status,
    )

    return {
        "total": len(adapters),
        "adapters": [
            {
                "id": a.id,
                "adapter_name": a.adapter_name,
                "adapter_type": a.adapter_type,
                "platform": a.platform,
                "persona": a.persona,
                "niche": a.niche,
                "status": a.status,
                "is_default": a.is_default,
                "training_samples": a.training_samples,
                "eval_metrics": a.eval_metrics,
                "created_at": a.created_at.isoformat(),
            }
            for a in adapters
        ]
    }


@router.get("/adapters/{adapter_name}")
async def get_adapter(
    adapter_name: str,
    db: Session = Depends(get_db)
):
    """获取 adapter 详情"""
    registry = AdapterRegistry(db)
    adapter = registry.get(adapter_name)

    if not adapter:
        raise HTTPException(status_code=404, detail=f"Adapter {adapter_name} 不存在")

    return {
        "id": adapter.id,
        "adapter_name": adapter.adapter_name,
        "adapter_type": adapter.adapter_type,
        "base_model": adapter.base_model,
        "adapter_path": adapter.adapter_path,
        "platform": adapter.platform,
        "persona": adapter.persona,
        "niche": adapter.niche,
        "status": adapter.status,
        "is_default": adapter.is_default,
        "training_config": adapter.training_config,
        "training_samples": adapter.training_samples,
        "training_epochs": adapter.training_epochs,
        "training_time_seconds": adapter.training_time_seconds,
        "eval_metrics": adapter.eval_metrics,
        "metadata": adapter.adapter_metadata,
        "created_at": adapter.created_at.isoformat(),
        "updated_at": adapter.updated_at.isoformat(),
    }


@router.post("/adapters/{adapter_name}/set-default")
async def set_default_adapter(
    adapter_name: str,
    db: Session = Depends(get_db)
):
    """设置默认 adapter"""
    registry = AdapterRegistry(db)

    try:
        registry.set_default(adapter_name)
        return {
            "status": "success",
            "message": f"Adapter {adapter_name} 已设置为默认"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/adapters/{adapter_name}/archive")
async def archive_adapter(
    adapter_name: str,
    db: Session = Depends(get_db)
):
    """归档 adapter"""
    registry = AdapterRegistry(db)

    try:
        registry.archive(adapter_name)
        return {
            "status": "success",
            "message": f"Adapter {adapter_name} 已归档"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ==================== Generation Endpoints ====================

@router.post("/generate")
async def generate(
    request: GenerateRequest,
    db: Session = Depends(get_db)
):
    """使用 adapter 生成文本"""
    registry = AdapterRegistry(db)
    loader = AdapterLoader(registry)

    try:
        result = loader.generate(
            prompt=request.prompt,
            adapter_name=request.adapter_name,
            platform=request.platform,
            persona=request.persona,
            niche=request.niche,
            max_new_tokens=request.max_new_tokens,
            temperature=request.temperature,
        )

        return {
            "status": "success",
            **result
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"生成失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Evaluation Endpoints ====================

@router.post("/evaluate/{adapter_name}")
async def evaluate_adapter(
    adapter_name: str,
    request: EvaluateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """评估 adapter（后台任务）"""
    logger.info(f"收到评估请求: {adapter_name}")

    def _evaluate():
        registry = AdapterRegistry(db)
        evaluator = Evaluator(registry)

        try:
            # 构建评估数据集
            from app.ml.training.dataset_builder import DatasetBuilder
            builder = DatasetBuilder(db)

            dataset = builder.build_sft_dataset(
                platform=request.platform or "xiaohongshu",
                days=7,
                max_samples=request.max_samples,
            )

            from datasets import Dataset as HFDataset
            eval_dataset = HFDataset.from_list(dataset.samples)

            # 评估
            metrics = evaluator.evaluate_adapter(
                adapter_name=adapter_name,
                eval_dataset=eval_dataset,
                platform=request.platform,
                max_samples=request.max_samples,
            )

            logger.info(f"评估完成: {metrics}")

        except Exception as e:
            logger.error(f"评估失败: {e}", exc_info=True)

    background_tasks.add_task(_evaluate)

    return {
        "status": "accepted",
        "message": f"评估任务已提交: {adapter_name}",
    }


@router.get("/evaluate/{adapter_name}/real-data")
async def evaluate_on_real_data(
    adapter_name: str,
    platform: str,
    days: int = 7,
    min_samples: int = 100,
    db: Session = Depends(get_db)
):
    """在真实数据上评估 adapter"""
    registry = AdapterRegistry(db)
    evaluator = Evaluator(registry)

    try:
        metrics = evaluator.evaluate_on_real_data(
            adapter_name=adapter_name,
            platform=platform,
            days=days,
            min_samples=min_samples,
        )

        return {
            "status": "success",
            "adapter_name": adapter_name,
            "metrics": metrics,
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"评估失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
