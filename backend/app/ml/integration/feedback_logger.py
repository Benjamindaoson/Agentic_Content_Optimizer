"""
用户反馈日志记录

记录用户对生成内容的反馈到 ML 训练数据库
ML 表已迁入 PostgreSQL，与主库统一
"""

import uuid
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.ml.training.schemas import Outcome

logger = logging.getLogger(__name__)


def _get_ml_engine():
    settings = get_settings()
    url = settings.DATABASE_URL
    if url.startswith("postgresql+asyncpg"):
        url = url.replace("postgresql+asyncpg://", "postgresql://")
    return create_engine(url, pool_pre_ping=True)


_ml_engine = None


def _get_ml_session():
    global _ml_engine
    if _ml_engine is None:
        _ml_engine = _get_ml_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=_ml_engine)


def log_user_feedback(
    trace_id: str,
    impressions: int = 0,
    clicks: int = 0,
    read_time_avg: float = 0.0,
    likes: int = 0,
    comments: int = 0,
    saves: int = 0,
    shares: int = 0,
    follows: int = 0,
) -> str:
    """
    记录用户反馈到 ML 训练数据库

    Args:
        trace_id: GenerationTrace ID
        impressions: 曝光数
        clicks: 点击数
        read_time_avg: 平均阅读时长（秒）
        likes: 点赞数
        comments: 评论数
        saves: 收藏数
        shares: 分享数
        follows: 关注数

    Returns:
        outcome_id: 反馈记录 ID
    """
    SessionLocal = _get_ml_session()
    ml_db = SessionLocal()

    try:
        # 计算衍生指标
        click_rate = clicks / impressions if impressions > 0 else 0.0
        completion_rate = min(read_time_avg / 60.0, 1.0)  # 假设 60 秒为完整阅读

        # 计算互动分
        from app.ml.training.dataset_builder import DatasetBuilder
        builder = DatasetBuilder(ml_db)

        outcome = Outcome(
            id=str(uuid.uuid4()),
            trace_id=trace_id,
            impressions=impressions,
            clicks=clicks,
            click_rate=click_rate,
            read_time_avg=read_time_avg,
            completion_rate=completion_rate,
            likes=likes,
            comments=comments,
            saves=saves,
            shares=shares,
            follows=follows,
        )

        # 计算 engagement_score
        outcome.engagement_score = builder.calculate_engagement_score(outcome)

        ml_db.add(outcome)
        ml_db.commit()
        ml_db.refresh(outcome)

        logger.info(f"记录 Outcome 成功: trace_id={trace_id}, engagement_score={outcome.engagement_score:.4f}")

        return outcome.id

    except Exception as e:
        ml_db.rollback()
        logger.error(f"记录 Outcome 失败: {e}")
        return None

    finally:
        ml_db.close()


def log_platform_metrics(
    trace_id: str,
    platform_data: dict,
) -> str:
    """
    从平台 API 获取的数据记录到 Outcome

    Args:
        trace_id: GenerationTrace ID
        platform_data: 平台数据，格式如：
            {
                "impressions": 1000,
                "likes": 50,
                "comments": 10,
                "saves": 30,
                "shares": 5,
                "read_time_avg": 45.0,
                ...
            }

    Returns:
        outcome_id: 反馈记录 ID
    """
    return log_user_feedback(
        trace_id=trace_id,
        impressions=platform_data.get("impressions", 0),
        clicks=platform_data.get("clicks", 0),
        read_time_avg=platform_data.get("read_time_avg", 0.0),
        likes=platform_data.get("likes", 0),
        comments=platform_data.get("comments", 0),
        saves=platform_data.get("saves", 0),
        shares=platform_data.get("shares", 0),
        follows=platform_data.get("follows", 0),
    )


# 使用示例：创建反馈收集 API 端点
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/ml/feedback", tags=["ml-feedback"])

class FeedbackRequest(BaseModel):
    trace_id: str
    impressions: int = 0
    clicks: int = 0
    read_time_avg: float = 0.0
    likes: int = 0
    comments: int = 0
    saves: int = 0
    shares: int = 0
    follows: int = 0

@router.post("/log")
async def log_feedback(request: FeedbackRequest):
    '''记录用户反馈'''
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
"""
