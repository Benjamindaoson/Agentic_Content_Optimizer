"""
ML 反馈收集 API

提供简单的 API 端点用于收集用户反馈
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from typing import Optional
import logging

from app.ml.integration.feedback_logger import log_user_feedback, log_platform_metrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ml/feedback", tags=["ml-feedback"])


class FeedbackRequest(BaseModel):
    """用户反馈请求"""
    trace_id: str = Field(..., description="GenerationTrace ID")
    impressions: int = Field(default=0, description="曝光数")
    clicks: int = Field(default=0, description="点击数")
    read_time_avg: float = Field(default=0.0, description="平均阅读时长（秒）")
    likes: int = Field(default=0, description="点赞数")
    comments: int = Field(default=0, description="评论数")
    saves: int = Field(default=0, description="收藏数")
    shares: int = Field(default=0, description="分享数")
    follows: int = Field(default=0, description="关注数")


class PlatformMetricsRequest(BaseModel):
    """平台数据请求"""
    trace_id: str = Field(..., description="GenerationTrace ID")
    platform_data: dict = Field(..., description="平台数据")


@router.post("/log")
async def log_feedback(request: FeedbackRequest):
    """
    记录用户反馈

    用于记录用户对生成内容的互动数据
    """
    try:
        outcome_id = log_user_feedback(
            trace_id=request.trace_id,
            impressions=request.impressions,
            clicks=request.clicks,
            read_time_avg=request.read_time_avg,
            likes=request.likes,
            comments=request.comments,
            saves=request.saves,
            shares=request.shares,
            follows=request.follows,
        )

        if outcome_id:
            return {
                "status": "success",
                "outcome_id": outcome_id,
                "message": "反馈记录成功"
            }
        else:
            raise HTTPException(status_code=500, detail="反馈记录失败")

    except Exception as e:
        logger.error(f"记录反馈失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/platform")
async def log_platform_data(request: PlatformMetricsRequest):
    """
    记录平台数据

    用于从平台 API 同步互动数据
    """
    try:
        outcome_id = log_platform_metrics(
            trace_id=request.trace_id,
            platform_data=request.platform_data,
        )

        if outcome_id:
            return {
                "status": "success",
                "outcome_id": outcome_id,
                "message": "平台数据记录成功"
            }
        else:
            raise HTTPException(status_code=500, detail="平台数据记录失败")

    except Exception as e:
        logger.error(f"记录平台数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_feedback_stats():
    """
    获取反馈统计

    返回当前收集的数据量
    """
    try:
        from app.core.config import get_settings
        from app.ml.training.schemas import GenerationTrace, Outcome

        settings = get_settings()
        url = settings.DATABASE_URL
        if url.startswith("postgresql+asyncpg"):
            url = url.replace("postgresql+asyncpg://", "postgresql://")
        engine = create_engine(url, pool_pre_ping=True)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        try:
            traces_count = db.query(GenerationTrace).count()
            outcomes_count = db.query(Outcome).count()

            # 计算平均互动分
            avg_engagement = db.query(func.avg(Outcome.engagement_score)).scalar() or 0.0

            return {
                "status": "success",
                "stats": {
                    "total_traces": traces_count,
                    "total_outcomes": outcomes_count,
                    "avg_engagement_score": round(avg_engagement, 4),
                    "ready_for_sft": traces_count >= 100,
                    "ready_for_dpo": outcomes_count >= 50,
                }
            }

        finally:
            db.close()

    except Exception as e:
        logger.error(f"获取统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
