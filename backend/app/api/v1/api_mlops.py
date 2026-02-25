"""
MLOps API

提供 MLOps 相关的监控和管理接口
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging

from app.mlops.mlflow_tracker import get_mlflow_tracker, MLflowConfig
from app.mlops.inference_cache import get_cache_manager
from app.mlops.performance_monitor import get_performance_monitor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mlops", tags=["mlops"])


class MLflowConfigRequest(BaseModel):
    """MLflow 配置请求"""
    tracking_uri: str = Field(default="sqlite:///mlflow.db", description="Tracking URI")
    experiment_name: str = Field(default="growth-flywheel", description="实验名称")
    enable_autolog: bool = Field(default=True, description="启用自动日志")


@router.get("/mlflow/experiments")
async def get_mlflow_experiments():
    """获取 MLflow 实验列表"""
    try:
        tracker = get_mlflow_tracker()
        summary = tracker.get_experiment_summary()

        return {
            "status": "success",
            "experiment": summary
        }

    except Exception as e:
        logger.error(f"Get experiments error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mlflow/runs/best")
async def get_best_run(
    metric_name: str = "viral_score",
    ascending: bool = False
):
    """获取最佳 run

    Args:
        metric_name: 指标名称
        ascending: 是否升序（越小越好）
    """
    try:
        tracker = get_mlflow_tracker()
        best_run = tracker.get_best_run(
            metric_name=metric_name,
            ascending=ascending
        )

        if best_run is None:
            return {
                "status": "no_runs",
                "message": "No runs found"
            }

        return {
            "status": "success",
            "run": {
                "run_id": best_run.info.run_id,
                "run_name": best_run.data.tags.get("mlflow.runName"),
                "metrics": best_run.data.metrics,
                "params": best_run.data.params,
                "start_time": best_run.info.start_time,
                "end_time": best_run.info.end_time
            }
        }

    except Exception as e:
        logger.error(f"Get best run error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mlflow/runs/compare")
async def compare_runs(
    run_ids: List[str],
    metric_names: List[str] = ["viral_score", "quality_score", "engagement_rate"]
):
    """对比多个 runs

    Args:
        run_ids: Run ID 列表
        metric_names: 指标名称列表
    """
    try:
        tracker = get_mlflow_tracker()
        comparison = tracker.compare_runs(
            run_ids=run_ids,
            metric_names=metric_names
        )

        return {
            "status": "success",
            "comparison": comparison
        }

    except Exception as e:
        logger.error(f"Compare runs error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/stats")
async def get_cache_stats():
    """获取缓存统计"""
    try:
        cache_manager = get_cache_manager()
        stats = cache_manager.get_overall_stats()

        return {
            "status": "success",
            "stats": stats
        }

    except Exception as e:
        logger.error(f"Get cache stats error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/clear")
async def clear_cache(cache_type: str = "all"):
    """清空缓存

    Args:
        cache_type: 缓存类型 (all/generation/rag/embedding)
    """
    try:
        cache_manager = get_cache_manager()

        if cache_type == "all":
            cache_manager.generation_cache.clear()
            cache_manager.rag_cache.clear()
            cache_manager.embedding_cache.clear()
            message = "All caches cleared"
        elif cache_type == "generation":
            cache_manager.generation_cache.clear()
            message = "Generation cache cleared"
        elif cache_type == "rag":
            cache_manager.rag_cache.clear()
            message = "RAG cache cleared"
        elif cache_type == "embedding":
            cache_manager.embedding_cache.clear()
            message = "Embedding cache cleared"
        else:
            raise HTTPException(status_code=400, detail="Invalid cache_type")

        return {
            "status": "success",
            "message": message
        }

    except Exception as e:
        logger.error(f"Clear cache error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/cleanup")
async def cleanup_expired_cache():
    """清理过期缓存"""
    try:
        cache_manager = get_cache_manager()

        total_cleaned = 0
        total_cleaned += cache_manager.generation_cache.cleanup_expired()
        total_cleaned += cache_manager.rag_cache.cleanup_expired()
        total_cleaned += cache_manager.embedding_cache.cleanup_expired()

        return {
            "status": "success",
            "message": f"Cleaned {total_cleaned} expired entries"
        }

    except Exception as e:
        logger.error(f"Cleanup cache error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/current")
async def get_current_performance():
    """获取当前性能指标"""
    try:
        monitor = get_performance_monitor()
        metrics = monitor.get_current_metrics()

        if metrics is None:
            return {
                "status": "no_data",
                "message": "No performance data available"
            }

        return {
            "status": "success",
            "metrics": {
                "timestamp": metrics.timestamp.isoformat(),
                "request_latency_ms": round(metrics.request_latency_ms, 2),
                "cpu_percent": round(metrics.cpu_percent, 2),
                "memory_percent": round(metrics.memory_percent, 2),
                "memory_mb": round(metrics.memory_mb, 2),
                "active_requests": metrics.active_requests,
                "throughput_rps": round(metrics.throughput_rps, 2)
            }
        }

    except Exception as e:
        logger.error(f"Get current performance error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/summary")
async def get_performance_summary(window_minutes: int = 5):
    """获取性能摘要

    Args:
        window_minutes: 时间窗口（分钟）
    """
    try:
        monitor = get_performance_monitor()
        summary = monitor.get_metrics_summary(window_minutes=window_minutes)

        return {
            "status": "success",
            "summary": summary
        }

    except Exception as e:
        logger.error(f"Get performance summary error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/alerts")
async def get_performance_alerts(
    limit: int = 10,
    severity: Optional[str] = None
):
    """获取性能告警

    Args:
        limit: 返回数量
        severity: 严重程度 (warning/critical)
    """
    try:
        monitor = get_performance_monitor()
        alerts = monitor.get_recent_alerts(limit=limit, severity=severity)

        return {
            "status": "success",
            "total": len(alerts),
            "alerts": [
                {
                    "alert_type": alert.alert_type,
                    "severity": alert.severity,
                    "message": alert.message,
                    "value": round(alert.value, 2),
                    "threshold": round(alert.threshold, 2),
                    "timestamp": alert.timestamp.isoformat(),
                    "suggestions": alert.suggestions
                }
                for alert in alerts
            ]
        }

    except Exception as e:
        logger.error(f"Get performance alerts error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/suggestions")
async def get_optimization_suggestions():
    """获取优化建议"""
    try:
        monitor = get_performance_monitor()
        suggestions = monitor.get_optimization_suggestions()

        return {
            "status": "success",
            "suggestions": suggestions
        }

    except Exception as e:
        logger.error(f"Get suggestions error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def mlops_health_check():
    """MLOps 健康检查"""
    try:
        # 检查各组件状态
        tracker = get_mlflow_tracker()
        cache_manager = get_cache_manager()
        monitor = get_performance_monitor()

        # MLflow 状态
        mlflow_status = "healthy"
        try:
            tracker.get_experiment_summary()
        except Exception:
            mlflow_status = "unhealthy"

        # 缓存状态
        cache_stats = cache_manager.get_overall_stats()
        cache_status = "healthy"

        # 性能监控状态
        perf_metrics = monitor.get_current_metrics()
        perf_status = "healthy" if perf_metrics else "no_data"

        overall_status = "healthy"
        if mlflow_status == "unhealthy" or cache_status == "unhealthy":
            overall_status = "degraded"

        return {
            "status": overall_status,
            "components": {
                "mlflow": mlflow_status,
                "cache": cache_status,
                "performance_monitor": perf_status
            },
            "cache_stats": {
                "generation_hit_rate": cache_stats["generation_cache"]["hit_rate"],
                "rag_hit_rate": cache_stats["rag_cache"]["hit_rate"],
                "total_size_mb": cache_stats["total_size_bytes"] / 1024 / 1024
            }
        }

    except Exception as e:
        logger.error(f"Health check error: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e)
        }
