"""
微调 API - 提供微调系统的 HTTP 接口

端点：
1. POST /api/finetune/trigger - 手动触发微调
2. GET /api/finetune/status - 获取微调状态
3. GET /api/finetune/models - 列出模型版本
4. POST /api/finetune/models/{version_id}/activate - 激活模型版本
5. GET /api/finetune/models/{version_id} - 获取模型详情
6. POST /api/finetune/evaluate - 评估模型
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.training import (
    FinetuneOrchestrator,
    FinetuneConfig,
    ModelManager
)
from app.ml.rl import EnhancedOnlineLearningLoop, EnhancedLearningConfig

router = APIRouter(prefix="/api/finetune", tags=["finetune"])

# 全局实例
_learning_loop: Optional[EnhancedOnlineLearningLoop] = None
_model_manager = ModelManager()


def get_learning_loop(db: Session = Depends(get_db)) -> EnhancedOnlineLearningLoop:
    """获取学习循环实例"""
    global _learning_loop
    if _learning_loop is None:
        config = EnhancedLearningConfig(
            grpo_training_interval_hours=24,
            dpo_finetune_interval_days=7,
            dpo_auto_deploy=False,
            enable_auto_finetune=True
        )
        _learning_loop = EnhancedOnlineLearningLoop(config=config, db=db)
    return _learning_loop


# ============================================================================
# Request/Response Models
# ============================================================================

class TriggerFinetuneRequest(BaseModel):
    """触发微调请求"""
    collection_days: int = 7
    preference_pairs_count: int = 500
    eval_threshold: float = 8.0
    auto_deploy: bool = False


class FinetuneStatusResponse(BaseModel):
    """微调状态响应"""
    is_running: bool
    grpo_learning: Dict[str, Any]
    dpo_finetuning: Dict[str, Any]
    performance: Dict[str, Any]


class ModelVersionResponse(BaseModel):
    """模型版本响应"""
    version_id: str
    model_path: str
    base_model: str
    training_method: str
    created_at: str
    metrics: Dict[str, float]
    is_active: bool


class ActivateModelRequest(BaseModel):
    """激活模型请求"""
    version_id: str


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/trigger")
async def trigger_finetune(
    request: TriggerFinetuneRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """手动触发 DPO 微调

    这将启动完整的微调周期：
    1. 收集线上数据
    2. 生成偏好对
    3. DPO/LoRA 训练
    4. 模型评估
    5. 模型部署
    6. 在线评估

    Args:
        request: 微调配置
        background_tasks: 后台任务
        db: 数据库会话

    Returns:
        触发结果
    """
    # 创建配置
    config = FinetuneConfig(
        collection_days=request.collection_days,
        preference_pairs_count=request.preference_pairs_count,
        eval_threshold=request.eval_threshold,
        auto_deploy=request.auto_deploy
    )

    # 创建编排器
    orchestrator = FinetuneOrchestrator(config=config, db=db)

    # 在后台运行微调
    async def run_finetune():
        result = await orchestrator.run_full_cycle()
        return result

    background_tasks.add_task(run_finetune)

    return {
        "status": "triggered",
        "message": "Finetune cycle started in background",
        "config": {
            "collection_days": request.collection_days,
            "preference_pairs_count": request.preference_pairs_count,
            "eval_threshold": request.eval_threshold,
            "auto_deploy": request.auto_deploy
        }
    }


@router.get("/status", response_model=FinetuneStatusResponse)
async def get_finetune_status(
    loop: EnhancedOnlineLearningLoop = Depends(get_learning_loop)
):
    """获取微调系统状态

    返回：
    - 学习循环是否运行
    - GRPO 训练状态
    - DPO 微调状态
    - 性能指标

    Returns:
        系统状态
    """
    status = loop.get_status()
    return FinetuneStatusResponse(**status)


@router.post("/start")
async def start_learning_loop(
    loop: EnhancedOnlineLearningLoop = Depends(get_learning_loop)
):
    """启动增强学习循环

    启动后将自动：
    - 每 24 小时运行 GRPO 策略学习
    - 每 7 天运行 DPO 模型微调

    Returns:
        启动结果
    """
    if loop.is_running:
        return {
            "status": "already_running",
            "message": "Learning loop is already running"
        }

    await loop.start()

    return {
        "status": "started",
        "message": "Enhanced learning loop started successfully",
        "config": {
            "grpo_interval_hours": loop.config.grpo_training_interval_hours,
            "dpo_interval_days": loop.config.dpo_finetune_interval_days,
            "auto_deploy": loop.config.dpo_auto_deploy
        }
    }


@router.post("/stop")
async def stop_learning_loop(
    loop: EnhancedOnlineLearningLoop = Depends(get_learning_loop)
):
    """停止增强学习循环

    Returns:
        停止结果
    """
    if not loop.is_running:
        return {
            "status": "not_running",
            "message": "Learning loop is not running"
        }

    await loop.stop()

    return {
        "status": "stopped",
        "message": "Enhanced learning loop stopped successfully"
    }


@router.post("/trigger-grpo")
async def trigger_grpo_training(
    loop: EnhancedOnlineLearningLoop = Depends(get_learning_loop)
):
    """手动触发 GRPO 策略学习

    GRPO 学习哪些策略组合效果好，不改变模型本身

    Returns:
        训练结果
    """
    result = await loop.trigger_grpo_training()

    return {
        "status": "success",
        "message": "GRPO training completed",
        "result": result
    }


@router.post("/trigger-dpo")
async def trigger_dpo_finetune(
    background_tasks: BackgroundTasks,
    loop: EnhancedOnlineLearningLoop = Depends(get_learning_loop)
):
    """手动触发 DPO 模型微调

    DPO 改进模型本身的生成能力，需要较长时间（1-2 小时）

    Returns:
        触发结果
    """
    # 在后台运行
    async def run_dpo():
        result = await loop.trigger_dpo_finetune()
        return result

    background_tasks.add_task(run_dpo)

    return {
        "status": "triggered",
        "message": "DPO finetuning started in background",
        "estimated_time": "1-2 hours"
    }


@router.get("/models")
async def list_models(
    training_method: Optional[str] = None,
    limit: int = 10
):
    """列出模型版本

    Args:
        training_method: 过滤训练方法（dpo, lora, sft）
        limit: 返回数量限制

    Returns:
        模型版本列表
    """
    versions = _model_manager.list_versions(
        training_method=training_method,
        limit=limit
    )

    return {
        "total": len(versions),
        "versions": [
            ModelVersionResponse(
                version_id=v.version_id,
                model_path=v.model_path,
                base_model=v.base_model,
                training_method=v.training_method,
                created_at=v.created_at.isoformat(),
                metrics=v.metrics,
                is_active=v.is_active
            )
            for v in versions
        ]
    }


@router.get("/models/{version_id}")
async def get_model_version(version_id: str):
    """获取模型版本详情

    Args:
        version_id: 版本 ID

    Returns:
        模型版本详情
    """
    version = _model_manager.get_version(version_id)

    if not version:
        raise HTTPException(status_code=404, detail="Model version not found")

    return ModelVersionResponse(
        version_id=version.version_id,
        model_path=version.model_path,
        base_model=version.base_model,
        training_method=version.training_method,
        created_at=version.created_at.isoformat(),
        metrics=version.metrics,
        is_active=version.is_active
    )


@router.post("/models/{version_id}/activate")
async def activate_model(version_id: str):
    """激活模型版本

    将指定版本设置为当前激活版本，用于生产环境

    Args:
        version_id: 版本 ID

    Returns:
        激活结果
    """
    try:
        _model_manager.activate_version(version_id)

        return {
            "status": "success",
            "message": f"Model version {version_id} activated",
            "version_id": version_id
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/models/active")
async def get_active_model():
    """获取当前激活的模型版本

    Returns:
        激活的模型版本
    """
    version = _model_manager.get_active_version()

    if not version:
        return {
            "status": "no_active_model",
            "message": "No model version is currently active"
        }

    return ModelVersionResponse(
        version_id=version.version_id,
        model_path=version.model_path,
        base_model=version.base_model,
        training_method=version.training_method,
        created_at=version.created_at.isoformat(),
        metrics=version.metrics,
        is_active=version.is_active
    )


@router.get("/models/best")
async def get_best_model(metric: str = "overall_score"):
    """获取最佳模型版本

    Args:
        metric: 评估指标

    Returns:
        最佳模型版本
    """
    version = _model_manager.get_best_version(metric=metric)

    if not version:
        return {
            "status": "no_models",
            "message": "No models found with the specified metric"
        }

    return ModelVersionResponse(
        version_id=version.version_id,
        model_path=version.model_path,
        base_model=version.base_model,
        training_method=version.training_method,
        created_at=version.created_at.isoformat(),
        metrics=version.metrics,
        is_active=version.is_active
    )


@router.get("/models/compare")
async def compare_models(version_id1: str, version_id2: str):
    """比较两个模型版本

    Args:
        version_id1: 版本 1 ID
        version_id2: 版本 2 ID

    Returns:
        比较结果
    """
    try:
        comparison = _model_manager.compare_versions(version_id1, version_id2)
        return comparison
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/stats")
async def get_stats():
    """获取微调系统统计信息

    Returns:
        统计信息
    """
    model_stats = _model_manager.get_stats()

    return {
        "model_manager": model_stats,
        "learning_loop": _learning_loop.get_status() if _learning_loop else None
    }
