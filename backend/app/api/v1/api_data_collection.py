"""
数据收集 API

提供内容生成记录和用户反馈收集的 API 端点
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import time

from app.core.database import get_db
from app.models.data_collection import ContentGenerationLog, UserFeedbackLog, ABTestLog


router = APIRouter(prefix="/api/data-collection", tags=["data-collection"])


# ==================== Pydantic Models ====================

class ContentGenerationRequest(BaseModel):
    """内容生成请求"""
    platform: str = Field(..., description="平台名称")
    topic: str = Field(..., description="主题")
    persona: Optional[str] = Field(None, description="目标用户画像")
    keywords: Optional[List[str]] = Field(None, description="关键词列表")
    additional_params: Optional[dict] = Field(None, description="其他参数")


class ContentGenerationLogRequest(BaseModel):
    """内容生成日志记录请求"""
    user_id: str
    session_id: Optional[str] = None
    platform: str
    topic: str
    persona: Optional[str] = None
    keywords: Optional[List[str]] = None
    additional_params: Optional[dict] = None

    model_version: str
    agent_config: Optional[dict] = None
    rag_enabled: bool = True
    rl_enabled: bool = True

    generated_content: str
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    cover_image_url: Optional[str] = None

    generation_time_ms: Optional[int] = None
    token_count: Optional[int] = None
    cost_usd: Optional[float] = None

    quality_score: Optional[float] = None
    platform_fit_score: Optional[float] = None
    viral_potential_score: Optional[float] = None


class UserFeedbackRequest(BaseModel):
    """用户反馈请求"""
    content_id: str = Field(..., description="内容 ID")
    user_id: str = Field(..., description="用户 ID")
    event_type: str = Field(..., description="事件类型: view, like, save, share, comment, click, convert")
    event_timestamp: Optional[int] = Field(None, description="事件时间戳（毫秒）")

    platform_post_id: Optional[str] = Field(None, description="平台帖子 ID")
    platform_metrics: Optional[dict] = Field(None, description="平台指标")

    rating: Optional[int] = Field(None, ge=1, le=5, description="评分 1-5")
    feedback_text: Optional[str] = Field(None, description="文字反馈")
    improvement_suggestions: Optional[List[str]] = Field(None, description="改进建议")

    conversion_type: Optional[str] = Field(None, description="转化类型")
    conversion_value: Optional[float] = Field(None, description="转化价值")


class ABTestLogRequest(BaseModel):
    """A/B 测试日志请求"""
    experiment_id: str
    variant_id: str
    content_id: str
    user_id: str
    experiment_config: dict
    outcome: Optional[str] = None
    outcome_value: Optional[float] = None


# ==================== API Endpoints ====================

@router.post("/content/log", status_code=status.HTTP_201_CREATED)
async def log_content_generation(
    request: ContentGenerationLogRequest,
    db: Session = Depends(get_db)
):
    """记录内容生成日志

    在每次内容生成后调用此接口，记录完整的生成信息
    """
    try:
        log = ContentGenerationLog(
            user_id=request.user_id,
            session_id=request.session_id,
            platform=request.platform,
            topic=request.topic,
            persona=request.persona,
            keywords=request.keywords,
            additional_params=request.additional_params,
            model_version=request.model_version,
            agent_config=request.agent_config,
            rag_enabled=request.rag_enabled,
            rl_enabled=request.rl_enabled,
            generated_content=request.generated_content,
            title=request.title,
            tags=request.tags,
            cover_image_url=request.cover_image_url,
            generation_time_ms=request.generation_time_ms,
            token_count=request.token_count,
            cost_usd=request.cost_usd,
            quality_score=request.quality_score,
            platform_fit_score=request.platform_fit_score,
            viral_potential_score=request.viral_potential_score,
        )

        db.add(log)
        db.commit()
        db.refresh(log)

        return {
            "status": "success",
            "content_id": log.id,
            "message": "内容生成日志已记录"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"记录失败: {str(e)}"
        )


@router.post("/feedback/log", status_code=status.HTTP_201_CREATED)
async def log_user_feedback(
    request: UserFeedbackRequest,
    db: Session = Depends(get_db)
):
    """记录用户反馈

    用户对生成内容的任何互动行为都应该记录
    """
    try:
        # 验证 content_id 存在
        content = db.query(ContentGenerationLog).filter_by(id=request.content_id).first()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"内容 ID {request.content_id} 不存在"
            )

        # 如果没有提供时间戳，使用当前时间
        event_timestamp = request.event_timestamp or int(time.time() * 1000)

        log = UserFeedbackLog(
            content_id=request.content_id,
            user_id=request.user_id,
            event_type=request.event_type,
            event_timestamp=event_timestamp,
            platform_post_id=request.platform_post_id,
            platform_metrics=request.platform_metrics,
            rating=request.rating,
            feedback_text=request.feedback_text,
            improvement_suggestions=request.improvement_suggestions,
            conversion_type=request.conversion_type,
            conversion_value=request.conversion_value,
        )

        db.add(log)
        db.commit()
        db.refresh(log)

        return {
            "status": "success",
            "feedback_id": log.id,
            "message": "用户反馈已记录"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"记录失败: {str(e)}"
        )


@router.post("/feedback/batch", status_code=status.HTTP_201_CREATED)
async def log_user_feedback_batch(
    requests: List[UserFeedbackRequest],
    db: Session = Depends(get_db)
):
    """批量记录用户反馈

    用于批量导入历史数据或定期同步平台数据
    """
    try:
        logs = []
        for request in requests:
            # 验证 content_id 存在
            content = db.query(ContentGenerationLog).filter_by(id=request.content_id).first()
            if not content:
                continue  # 跳过不存在的内容

            event_timestamp = request.event_timestamp or int(time.time() * 1000)

            log = UserFeedbackLog(
                content_id=request.content_id,
                user_id=request.user_id,
                event_type=request.event_type,
                event_timestamp=event_timestamp,
                platform_post_id=request.platform_post_id,
                platform_metrics=request.platform_metrics,
                rating=request.rating,
                feedback_text=request.feedback_text,
                improvement_suggestions=request.improvement_suggestions,
                conversion_type=request.conversion_type,
                conversion_value=request.conversion_value,
            )
            logs.append(log)

        db.add_all(logs)
        db.commit()

        return {
            "status": "success",
            "count": len(logs),
            "message": f"成功记录 {len(logs)} 条反馈"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量记录失败: {str(e)}"
        )


@router.get("/content/{content_id}")
async def get_content_log(
    content_id: str,
    db: Session = Depends(get_db)
):
    """获取内容生成日志"""
    content = db.query(ContentGenerationLog).filter_by(id=content_id).first()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"内容 ID {content_id} 不存在"
        )

    return {
        "id": content.id,
        "user_id": content.user_id,
        "platform": content.platform,
        "topic": content.topic,
        "persona": content.persona,
        "model_version": content.model_version,
        "generated_content": content.generated_content,
        "quality_score": content.quality_score,
        "aggregated_metrics": content.aggregated_metrics,
        "created_at": content.created_at.isoformat(),
    }


@router.get("/content/{content_id}/feedbacks")
async def get_content_feedbacks(
    content_id: str,
    db: Session = Depends(get_db)
):
    """获取内容的所有反馈"""
    content = db.query(ContentGenerationLog).filter_by(id=content_id).first()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"内容 ID {content_id} 不存在"
        )

    feedbacks = db.query(UserFeedbackLog).filter_by(content_id=content_id).all()

    return {
        "content_id": content_id,
        "total_feedbacks": len(feedbacks),
        "feedbacks": [
            {
                "id": f.id,
                "user_id": f.user_id,
                "event_type": f.event_type,
                "event_timestamp": f.event_timestamp,
                "rating": f.rating,
                "created_at": f.created_at.isoformat(),
            }
            for f in feedbacks
        ]
    }


@router.get("/stats/daily")
async def get_daily_stats(
    date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取每日统计数据

    Args:
        date: 日期（YYYY-MM-DD），默认为今天
    """
    if date:
        target_date = datetime.strptime(date, "%Y-%m-%d")
    else:
        target_date = datetime.now()

    start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    # 统计内容生成
    contents = db.query(ContentGenerationLog).filter(
        ContentGenerationLog.created_at >= start,
        ContentGenerationLog.created_at < end
    ).all()

    # 统计反馈
    feedbacks = db.query(UserFeedbackLog).filter(
        UserFeedbackLog.created_at >= start,
        UserFeedbackLog.created_at < end
    ).all()

    # 按平台统计
    by_platform = {}
    for content in contents:
        platform = content.platform
        if platform not in by_platform:
            by_platform[platform] = 0
        by_platform[platform] += 1

    # 按事件类型统计
    by_event_type = {}
    for feedback in feedbacks:
        event_type = feedback.event_type
        if event_type not in by_event_type:
            by_event_type[event_type] = 0
        by_event_type[event_type] += 1

    return {
        "date": target_date.strftime("%Y-%m-%d"),
        "total_contents": len(contents),
        "total_feedbacks": len(feedbacks),
        "feedback_rate": len(feedbacks) / len(contents) if contents else 0,
        "by_platform": by_platform,
        "by_event_type": by_event_type,
    }


@router.post("/ab-test/log", status_code=status.HTTP_201_CREATED)
async def log_ab_test(
    request: ABTestLogRequest,
    db: Session = Depends(get_db)
):
    """记录 A/B 测试日志"""
    try:
        log = ABTestLog(
            experiment_id=request.experiment_id,
            variant_id=request.variant_id,
            content_id=request.content_id,
            user_id=request.user_id,
            experiment_config=request.experiment_config,
            outcome=request.outcome,
            outcome_value=request.outcome_value,
        )

        db.add(log)
        db.commit()
        db.refresh(log)

        return {
            "status": "success",
            "ab_test_id": log.id,
            "message": "A/B 测试日志已记录"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"记录失败: {str(e)}"
        )
