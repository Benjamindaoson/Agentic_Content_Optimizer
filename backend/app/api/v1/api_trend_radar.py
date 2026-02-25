"""
热点雷达 API

运营人员手动触发刷新，查看实时热点，选择要追的话题。
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_active_user
from app.models.user import User

router = APIRouter(prefix="/api/v1/trends", tags=["trends"])


@router.get("/radar")
async def get_trend_radar(
    niche: Optional[str] = Query(None, description="账号定位（如 护肤、穿搭）"),
    limit: int = Query(30, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
):
    """
    获取实时热点雷达数据。
    缓存 30 分钟，多次请求不会重复抓取。
    """
    from app.engine.trend_radar import TrendRadar

    radar = TrendRadar()
    trends = await radar.scan(account_niche=niche or "")

    return {
        "success": True,
        "count": min(len(trends), limit),
        "trends": [
            {
                "keyword": t.keyword,
                "score": t.score,
                "heat": t.heat,
                "sources": t.sources,
                "category": t.category,
                "account_fit": t.account_fit,
            }
            for t in trends[:limit]
        ],
    }


@router.get("/check")
async def check_topic_heat(
    topic: str = Query(..., description="要查询热度的话题"),
    current_user: User = Depends(get_current_active_user),
):
    """查询特定话题的热度，如果不热则建议替代话题"""
    from app.engine.trend_radar import TrendRadar

    radar = TrendRadar()
    heat = await radar.get_topic_heat(topic)

    result = {"topic": topic, "is_hot": False, "heat_info": None, "alternatives": []}

    if heat and heat.score > 0.3:
        result["is_hot"] = True
        result["heat_info"] = {
            "score": heat.score,
            "heat": heat.heat,
            "sources": heat.sources,
        }
    else:
        alternatives = await radar.suggest_alternatives(topic)
        result["alternatives"] = [
            {"keyword": a.keyword, "score": a.score, "sources": a.sources}
            for a in alternatives
        ]

    return result
