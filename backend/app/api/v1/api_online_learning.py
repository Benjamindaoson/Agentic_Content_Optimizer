"""
在线学习 API

提供在线学习循环的监控和控制端点
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging

from app.ml.rl.online_learning_loop import get_learning_loop, LearningLoopConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/online-learning", tags=["online-learning"])


class StartLoopRequest(BaseModel):
    """启动学习循环请求"""
    collection_interval_hours: int = Field(default=6, description="指标收集间隔（小时）")
    training_interval_hours: int = Field(default=24, description="训练间隔（小时）")
    collection_lookback_days: int = Field(default=7, description="收集数据回溯天数")
    training_lookback_days: int = Field(default=7, description="训练数据回溯天数")
    min_samples_per_pattern: int = Field(default=3, description="每个模式最小样本数")
    enable_auto_training: bool = Field(default=True, description="是否自动训练")


class TriggerCollectionRequest(BaseModel):
    """触发收集请求"""
    lookback_days: int = Field(default=7, description="回溯天数")


class TriggerTrainingRequest(BaseModel):
    """触发训练请求"""
    lookback_days: int = Field(default=7, description="训练数据回溯天数")
    min_samples_per_pattern: int = Field(default=3, description="每个模式最小样本数")


@router.post("/start")
async def start_learning_loop(request: StartLoopRequest):
    """启动在线学习循环

    开始自动收集指标和训练模型
    """
    try:
        loop = get_learning_loop()

        # 更新配置
        loop.config = LearningLoopConfig(
            collection_interval_hours=request.collection_interval_hours,
            training_interval_hours=request.training_interval_hours,
            collection_lookback_days=request.collection_lookback_days,
            training_lookback_days=request.training_lookback_days,
            min_samples_per_pattern=request.min_samples_per_pattern,
            enable_auto_training=request.enable_auto_training
        )

        # 启动循环
        await loop.start()

        return {
            'status': 'success',
            'message': 'Online learning loop started',
            'config': {
                'collection_interval_hours': request.collection_interval_hours,
                'training_interval_hours': request.training_interval_hours,
                'collection_lookback_days': request.collection_lookback_days,
                'training_lookback_days': request.training_lookback_days,
                'min_samples_per_pattern': request.min_samples_per_pattern,
                'enable_auto_training': request.enable_auto_training
            }
        }

    except Exception as e:
        logger.error(f"Start learning loop error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_learning_loop():
    """停止在线学习循环

    停止自动收集和训练
    """
    try:
        loop = get_learning_loop()
        await loop.stop()

        return {
            'status': 'success',
            'message': 'Online learning loop stopped'
        }

    except Exception as e:
        logger.error(f"Stop learning loop error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_learning_loop_status():
    """获取学习循环状态

    返回当前运行状态、统计信息和下次执行时间
    """
    try:
        loop = get_learning_loop()
        status = loop.get_status()

        return {
            'status': 'success',
            'learning_loop': {
                'is_running': status.is_running,
                'last_collection_at': status.last_collection_at.isoformat() if status.last_collection_at else None,
                'last_training_at': status.last_training_at.isoformat() if status.last_training_at else None,
                'next_collection_at': status.next_collection_at.isoformat() if status.next_collection_at else None,
                'next_training_at': status.next_training_at.isoformat() if status.next_training_at else None,
                'statistics': {
                    'total_collections': status.total_collections,
                    'total_trainings': status.total_trainings,
                    'total_samples_collected': status.total_samples_collected,
                    'total_patterns_updated': status.total_patterns_updated,
                    'avg_improvement': round(status.avg_improvement, 4)
                }
            }
        }

    except Exception as e:
        logger.error(f"Get status error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger/collection")
async def trigger_collection(background_tasks: BackgroundTasks):
    """手动触发指标收集

    立即执行一次指标收集，不影响定时任务
    """
    try:
        loop = get_learning_loop()

        # 在后台执行收集
        result = await loop.trigger_collection()

        return {
            'status': 'success',
            'message': 'Metrics collection triggered',
            'result': result
        }

    except Exception as e:
        logger.error(f"Trigger collection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger/training")
async def trigger_training(background_tasks: BackgroundTasks):
    """手动触发 GRPO 训练

    立即执行一次训练，不影响定时任务
    """
    try:
        loop = get_learning_loop()

        # 在后台执行训练
        result = await loop.trigger_training()

        return {
            'status': 'success',
            'message': 'GRPO training triggered',
            'result': result
        }

    except Exception as e:
        logger.error(f"Trigger training error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance")
async def get_recent_performance(days: int = 7):
    """获取最近的性能统计

    Args:
        days: 统计天数（默认7天）

    Returns:
        性能统计数据
    """
    try:
        loop = get_learning_loop()
        performance = await loop.get_recent_performance(days=days)

        return {
            'status': 'success',
            'performance': performance
        }

    except Exception as e:
        logger.error(f"Get performance error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/training/history")
async def get_training_history(limit: int = 10):
    """获取训练历史

    Args:
        limit: 返回数量（默认10）

    Returns:
        训练历史列表
    """
    try:
        loop = get_learning_loop()

        # 获取训练历史
        from app.db import get_db
        db = next(get_db())

        try:
            history = await loop.grpo_trainer.get_training_history(
                limit=limit,
                db=db
            )

            return {
                'status': 'success',
                'total': len(history),
                'history': history
            }

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Get training history error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prediction/accuracy")
async def get_prediction_accuracy(days: int = 7):
    """获取预测准确性评估

    Args:
        days: 评估天数（默认7天）

    Returns:
        准确性报告
    """
    try:
        loop = get_learning_loop()

        # 获取数据库会话
        from app.db import get_db
        db = next(get_db())

        try:
            accuracy = await loop.grpo_trainer.evaluate_prediction_accuracy(
                days=days,
                db=db
            )

            return {
                'status': 'success',
                'accuracy': accuracy
            }

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Get prediction accuracy error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/patterns/performance")
async def get_patterns_performance():
    """获取所有模式的性能统计

    Returns:
        模式性能列表
    """
    try:
        from app.db import get_db, Pattern
        db = next(get_db())

        try:
            # 查询所有模式
            patterns = db.query(Pattern).filter(
                Pattern.sample_size > 0
            ).order_by(Pattern.success_rate.desc()).all()

            pattern_list = []

            for pattern in patterns:
                pattern_list.append({
                    'pattern_id': pattern.pattern_id,
                    'pattern_name': pattern.pattern_name,
                    'success_rate': round(pattern.success_rate or 0, 4),
                    'sample_size': pattern.sample_size or 0,
                    'avg_viral_score': round(pattern.avg_viral_score or 0, 4),
                    'thompson_alpha': round(pattern.thompson_alpha or 1, 2),
                    'thompson_beta': round(pattern.thompson_beta or 1, 2),
                    'last_trained_at': pattern.last_trained_at.isoformat() if pattern.last_trained_at else None
                })

            return {
                'status': 'success',
                'total_patterns': len(pattern_list),
                'patterns': pattern_list
            }

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Get patterns performance error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """健康检查

    检查在线学习系统是否正常运行
    """
    try:
        loop = get_learning_loop()
        status = loop.get_status()

        # 检查是否有异常
        warnings = []

        if status.is_running:
            # 检查最近是否有收集
            if status.last_collection_at:
                from datetime import datetime, timedelta
                hours_since_collection = (
                    datetime.now() - status.last_collection_at
                ).total_seconds() / 3600

                if hours_since_collection > loop.config.collection_interval_hours * 2:
                    warnings.append(
                        f"No collection for {hours_since_collection:.1f} hours"
                    )

            # 检查最近是否有训练
            if status.last_training_at:
                hours_since_training = (
                    datetime.now() - status.last_training_at
                ).total_seconds() / 3600

                if hours_since_training > loop.config.training_interval_hours * 2:
                    warnings.append(
                        f"No training for {hours_since_training:.1f} hours"
                    )

        health_status = 'healthy' if not warnings else 'warning'

        return {
            'status': health_status,
            'is_running': status.is_running,
            'warnings': warnings,
            'statistics': {
                'total_collections': status.total_collections,
                'total_trainings': status.total_trainings,
                'total_samples_collected': status.total_samples_collected,
                'total_patterns_updated': status.total_patterns_updated
            }
        }

    except Exception as e:
        logger.error(f"Health check error: {e}", exc_info=True)
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
