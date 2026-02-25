"""
数据工程 API

提供数据合成和评估接口
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging

from app.data.data_engineering.synthetic_data_generator import get_synthetic_data_generator
from app.data.data_engineering.agent_benchmark import get_agent_benchmark

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data-engineering", tags=["data-engineering"])


class GenerateTopicsRequest(BaseModel):
    """生成主题请求"""
    num_topics: int = Field(default=100, description="主题数量")
    categories: Optional[List[str]] = Field(None, description="主题类别")


class GenerateDatasetRequest(BaseModel):
    """生成数据集请求"""
    num_samples: int = Field(default=100, description="样本数量")
    platforms: Optional[List[str]] = Field(None, description="平台列表")
    quality_distribution: Optional[Dict[str, float]] = Field(None, description="质量分布")
    save_to_file: bool = Field(default=False, description="是否保存到文件")
    output_file: Optional[str] = Field(None, description="输出文件路径")


class GeneratePreferenceDatasetRequest(BaseModel):
    """生成偏好对数据集请求"""
    num_pairs: int = Field(default=50, description="偏好对数量")
    platforms: Optional[List[str]] = Field(None, description="平台列表")
    save_to_file: bool = Field(default=False, description="是否保存到文件")
    output_file: Optional[str] = Field(None, description="输出文件路径")


class RunBenchmarkRequest(BaseModel):
    """运行基准测试请求"""
    use_default_tasks: bool = Field(default=True, description="使用默认任务")
    custom_tasks: Optional[List[Dict[str, Any]]] = Field(None, description="自定义任务")
    max_concurrent: int = Field(default=3, description="最大并发数")
    save_report: bool = Field(default=False, description="是否保存报告")
    output_file: Optional[str] = Field(None, description="输出文件路径")


@router.post("/synthetic/topics")
async def generate_topics(request: GenerateTopicsRequest):
    """生成主题列表"""
    try:
        generator = get_synthetic_data_generator()

        topics = await generator.generate_topics(
            num_topics=request.num_topics,
            categories=request.categories
        )

        return {
            "status": "success",
            "total": len(topics),
            "topics": topics
        }

    except Exception as e:
        logger.error(f"Generate topics error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/synthetic/dataset")
async def generate_dataset(
    request: GenerateDatasetRequest,
    background_tasks: BackgroundTasks
):
    """生成合成数据集"""
    try:
        generator = get_synthetic_data_generator()

        # 生成数据集
        samples = await generator.generate_dataset(
            num_samples=request.num_samples,
            platforms=request.platforms,
            quality_distribution=request.quality_distribution
        )

        # 保存到文件（如果需要）
        if request.save_to_file and request.output_file:
            generator.save_dataset(samples, request.output_file)

        # 返回摘要
        quality_counts = {}
        for sample in samples:
            level = sample.metadata.get("quality_level", "unknown")
            quality_counts[level] = quality_counts.get(level, 0) + 1

        return {
            "status": "success",
            "total_samples": len(samples),
            "quality_distribution": quality_counts,
            "platforms": list(set(s.platform for s in samples)),
            "avg_quality_score": sum(s.quality_score for s in samples) / len(samples),
            "saved_to_file": request.save_to_file,
            "output_file": request.output_file if request.save_to_file else None
        }

    except Exception as e:
        logger.error(f"Generate dataset error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/synthetic/preference-dataset")
async def generate_preference_dataset(
    request: GeneratePreferenceDatasetRequest,
    background_tasks: BackgroundTasks
):
    """生成偏好对数据集（用于 DPO）"""
    try:
        generator = get_synthetic_data_generator()

        # 生成偏好对
        pairs = await generator.generate_preference_dataset(
            num_pairs=request.num_pairs,
            platforms=request.platforms
        )

        # 保存到文件（如果需要）
        if request.save_to_file and request.output_file:
            generator.save_preference_dataset(pairs, request.output_file)

        # 返回摘要
        avg_score_diff = sum(
            p.chosen_score - p.rejected_score for p in pairs
        ) / len(pairs)

        return {
            "status": "success",
            "total_pairs": len(pairs),
            "platforms": list(set(p.platform for p in pairs)),
            "avg_chosen_score": sum(p.chosen_score for p in pairs) / len(pairs),
            "avg_rejected_score": sum(p.rejected_score for p in pairs) / len(pairs),
            "avg_score_difference": avg_score_diff,
            "saved_to_file": request.save_to_file,
            "output_file": request.output_file if request.save_to_file else None
        }

    except Exception as e:
        logger.error(f"Generate preference dataset error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/benchmark/run")
async def run_benchmark(
    request: RunBenchmarkRequest,
    background_tasks: BackgroundTasks
):
    """运行 Agent 基准测试"""
    try:
        benchmark = get_agent_benchmark()

        # 准备任务
        tasks = None
        if not request.use_default_tasks and request.custom_tasks:
            from app.data.data_engineering.agent_benchmark import BenchmarkTask
            tasks = [BenchmarkTask(**task) for task in request.custom_tasks]

        # 运行基准测试
        report = await benchmark.run_benchmark(
            tasks=tasks,
            max_concurrent=request.max_concurrent
        )

        # 保存报告（如果需要）
        if request.save_report and request.output_file:
            benchmark.save_report(report, request.output_file)

        return {
            "status": "success",
            "summary": {
                "total_tasks": report.total_tasks,
                "successful_tasks": report.successful_tasks,
                "failed_tasks": report.failed_tasks,
                "success_rate": round(report.success_rate, 4),
                "avg_quality_score": round(report.avg_quality_score, 4),
                "avg_execution_time": round(report.avg_execution_time, 2),
                "avg_retries": round(report.avg_retries, 2)
            },
            "quality_distribution": report.quality_distribution,
            "difficulty_breakdown": {
                k: {
                    "total": v["total"],
                    "successful": v["successful"],
                    "success_rate": round(v["success_rate"], 4),
                    "avg_quality": round(v["avg_quality"], 4)
                }
                for k, v in report.difficulty_breakdown.items()
            },
            "saved_report": request.save_report,
            "output_file": request.output_file if request.save_report else None
        }

    except Exception as e:
        logger.error(f"Run benchmark error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/benchmark/default-tasks")
async def get_default_benchmark_tasks():
    """获取默认基准测试任务"""
    try:
        benchmark = get_agent_benchmark()
        tasks = benchmark.create_default_tasks()

        return {
            "status": "success",
            "total": len(tasks),
            "tasks": [
                {
                    "task_id": task.task_id,
                    "topic": task.topic,
                    "platform": task.platform,
                    "difficulty": task.difficulty,
                    "expected_quality": task.expected_quality,
                    "timeout_seconds": task.timeout_seconds
                }
                for task in tasks
            ]
        }

    except Exception as e:
        logger.error(f"Get default tasks error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def data_engineering_health_check():
    """数据工程健康检查"""
    try:
        # 检查组件状态
        generator = get_synthetic_data_generator()
        benchmark = get_agent_benchmark()

        return {
            "status": "healthy",
            "components": {
                "synthetic_data_generator": "ready",
                "agent_benchmark": "ready"
            }
        }

    except Exception as e:
        logger.error(f"Health check error: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e)
        }
