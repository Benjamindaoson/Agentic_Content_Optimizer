"""
v4.0 Growth Brain RAG API 路由

提供 RAG 检索增强生成的 API 端点
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.engine.growth_brain.auto_account_manager import AutoAccountManager
from app.engine.growth_brain.multimodal_cover_engine import MultimodalCoverEngine
from app.engine.growth_brain.multi_platform_engine import MultiPlatformEngine
from app.engine.growth_brain.causal_inference_engine import CausalInferenceEngine

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])


# ==================== 请求/响应模型 ====================

class RetrieveTopicsRequest(BaseModel):
    persona_keywords: List[str]
    limit: int = 10


class GenerateContentRequest(BaseModel):
    topic: str
    style: str
    persona: dict


class RetrieveCoversRequest(BaseModel):
    topic: str
    style: str
    min_ctr: float = 0.05
    limit: int = 10


class AdaptContentRequest(BaseModel):
    content: str
    source_platform: str
    target_platform: str


class InferCausalRequest(BaseModel):
    treatment: str
    outcome: str
    confounders: List[str]


# ==================== Auto Account Manager RAG ====================

@router.post("/account/retrieve-topics")
async def retrieve_successful_topics(
    request: RetrieveTopicsRequest,
    db: Session = Depends(get_db)
):
    """
    检索历史成功话题

    使用 RAG 从知识库检索相关成功话题
    """
    manager = AutoAccountManager(db, enable_rag=True, enable_rl=False)

    results = await manager.retrieve_successful_topics(
        persona_keywords=request.persona_keywords,
        limit=request.limit
    )

    return {
        "status": "success",
        "topics": results
    }


@router.post("/account/recommend-topics")
async def recommend_topics_with_rag(
    account_id: str,
    persona_keywords: List[str],
    k: int = 3,
    db: Session = Depends(get_db)
):
    """
    使用 RAG 推荐话题

    结合检索和学习推荐最优话题
    """
    manager = AutoAccountManager(db, enable_rag=True, enable_rl=False)

    recommendations = await manager.recommend_topics_with_rag(
        account_id=account_id,
        persona_keywords=persona_keywords,
        k=k
    )

    return {
        "status": "success",
        "recommendations": recommendations
    }


@router.post("/account/generate-content")
async def generate_content_with_rag(
    request: GenerateContentRequest,
    db: Session = Depends(get_db)
):
    """
    使用 RAG 生成内容

    检索相似爆款内容作为参考
    """
    rag = AutoAccountManager(db, enable_rag=True, enable_rl=False)(db)

    result = await rag.generate_content_with_rag(
        topic=request.topic,
        style=request.style,
        persona=request.persona
    )

    return result


@router.get("/account/learn-patterns")
async def learn_success_patterns(
    account_id: str,
    days: int = 30,
    db: Session = Depends(get_db)
):
    """
    学习成功模式

    分析历史成功内容,提取模式
    """
    rag = AutoAccountManager(db, enable_rag=True, enable_rl=False)(db)

    patterns = await rag.learn_success_patterns(
        account_id=account_id,
        days=days
    )

    return patterns


# ==================== Multimodal Cover Engine RAG ====================

@router.post("/cover/retrieve-high-ctr")
async def retrieve_high_ctr_covers(
    request: RetrieveCoversRequest,
    db: Session = Depends(get_db)
):
    """
    检索高 CTR 封面

    从知识库检索高点击率封面作为参考
    """
    rag = MultimodalCoverEngine(db, enable_rag=True, enable_rl=False)(db)

    results = await rag.retrieve_high_ctr_covers(
        topic=request.topic,
        style=request.style,
        min_ctr=request.min_ctr,
        limit=request.limit
    )

    return {
        "status": "success",
        "covers": results
    }


@router.post("/cover/generate-with-rag")
async def generate_cover_with_rag(
    topic: str,
    style: str,
    generator: str = "dalle",
    db: Session = Depends(get_db)
):
    """
    使用 RAG 生成封面

    检索高性能封面,学习视觉特征,生成新封面
    """
    rag = MultimodalCoverEngine(db, enable_rag=True, enable_rl=False)(db)

    result = await rag.generate_cover_with_rag(
        topic=topic,
        style=style,
        generator=generator
    )

    return result


@router.get("/cover/optimize")
async def optimize_cover_with_rag(
    cover_id: str,
    db: Session = Depends(get_db)
):
    """
    使用 RAG 优化封面

    检索相似高性能封面,生成优化建议
    """
    rag = MultimodalCoverEngine(db, enable_rag=True, enable_rl=False)(db)

    result = await rag.optimize_cover_with_rag(cover_id=cover_id)

    return result


@router.get("/cover/similar")
async def find_similar_covers(
    cover_id: str,
    limit: int = 5,
    db: Session = Depends(get_db)
):
    """
    查找相似封面

    基于向量相似度检索
    """
    rag = MultimodalCoverEngine(db, enable_rag=True, enable_rl=False)(db)

    results = await rag.find_similar_covers(
        cover_id=cover_id,
        limit=limit
    )

    return {
        "status": "success",
        "similar_covers": results
    }


# ==================== Multi Platform Engine RAG ====================

@router.get("/platform/best-practices")
async def retrieve_platform_best_practices(
    platform: str,
    content_type: str,
    min_engagement: float = 0.1,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    检索平台最佳实践

    从知识库检索该平台的高性能内容
    """
    rag = MultiPlatformEngine(db, enable_rag=True, enable_rl=False)(db)

    results = await rag.retrieve_platform_best_practices(
        platform=platform,
        content_type=content_type,
        min_engagement=min_engagement,
        limit=limit
    )

    return {
        "status": "success",
        "best_practices": results
    }


@router.post("/platform/adapt-content")
async def adapt_content_with_rag(
    request: AdaptContentRequest,
    db: Session = Depends(get_db)
):
    """
    使用 RAG 适配内容

    检索目标平台最佳实践,生成适配建议
    """
    rag = MultiPlatformEngine(db, enable_rag=True, enable_rl=False)(db)

    result = await rag.adapt_content_with_rag(
        content=request.content,
        source_platform=request.source_platform,
        target_platform=request.target_platform
    )

    return result


@router.get("/platform/learn-style")
async def learn_platform_style(
    platform: str,
    sample_size: int = 50,
    db: Session = Depends(get_db)
):
    """
    学习平台风格

    分析平台高性能内容,提取风格特征
    """
    rag = MultiPlatformEngine(db, enable_rag=True, enable_rl=False)(db)

    result = await rag.learn_platform_style(
        platform=platform,
        sample_size=sample_size
    )

    return result


@router.get("/platform/transfer-knowledge")
async def cross_platform_knowledge_transfer(
    source_platform: str,
    target_platform: str,
    db: Session = Depends(get_db)
):
    """
    跨平台知识迁移

    分析平台差异,生成迁移策略
    """
    rag = MultiPlatformEngine(db, enable_rag=True, enable_rl=False)(db)

    result = await rag.cross_platform_knowledge_transfer(
        source_platform=source_platform,
        target_platform=target_platform
    )

    return result


# ==================== Causal Inference Engine RAG ====================

@router.get("/causal/retrieve-cases")
async def retrieve_causal_cases(
    treatment: str,
    outcome: str,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    检索因果关系案例

    从知识库检索相似因果关系
    """
    rag = CausalInferenceEngine(db, enable_rag=True, enable_rl=False)(db)

    results = await rag.retrieve_causal_cases(
        treatment=treatment,
        outcome=outcome,
        limit=limit
    )

    return {
        "status": "success",
        "cases": results
    }


@router.post("/causal/infer-with-rag")
async def infer_with_rag(
    request: InferCausalRequest,
    db: Session = Depends(get_db)
):
    """
    使用 RAG 辅助因果推断

    检索相似案例,加权估计因果效应
    """
    rag = CausalInferenceEngine(db, enable_rag=True, enable_rl=False)(db)

    result = await rag.infer_with_rag(
        treatment=request.treatment,
        outcome=request.outcome,
        confounders=request.confounders
    )

    return result


@router.get("/causal/find-confounders")
async def find_confounders_with_rag(
    treatment: str,
    outcome: str,
    db: Session = Depends(get_db)
):
    """
    使用 RAG 查找混淆变量

    从相似案例中提取常见混淆变量
    """
    rag = CausalInferenceEngine(db, enable_rag=True, enable_rl=False)(db)

    confounders = await rag.find_confounders_with_rag(
        treatment=treatment,
        outcome=outcome
    )

    return {
        "status": "success",
        "confounders": confounders
    }


@router.post("/causal/validate-hypothesis")
async def validate_causal_hypothesis(
    hypothesis: str,
    db: Session = Depends(get_db)
):
    """
    使用 RAG 验证因果假设

    检索相关证据,统计支持/反对比例
    """
    rag = CausalInferenceEngine(db, enable_rag=True, enable_rl=False)(db)

    result = await rag.validate_causal_hypothesis_with_rag(
        hypothesis=hypothesis
    )

    return result


@router.get("/causal/learn-patterns")
async def learn_causal_patterns(
    domain: str,
    sample_size: int = 50,
    db: Session = Depends(get_db)
):
    """
    学习因果模式

    分析领域内的因果关系,提取模式
    """
    rag = CausalInferenceEngine(db, enable_rag=True, enable_rl=False)(db)

    result = await rag.learn_causal_patterns(
        domain=domain,
        sample_size=sample_size
    )

    return result


# ==================== 通用 RAG 端点 ====================

@router.get("/status")
async def get_rag_status(db: Session = Depends(get_db)):
    """
    获取 RAG 系统状态

    返回所有 RAG 组件的状态
    """
    return {
        "status": "operational",
        "components": {
            "auto_account_manager": "enabled",
            "multimodal_cover_engine": "enabled",
            "multi_platform_engine": "enabled",
            "causal_inference_engine": "enabled"
        },
        "algorithms": {
            "self_rag": "enabled",
            "crag": "enabled",
            "adaptive_rag": "enabled",
            "graph_rag": "enabled",
            "multi_hop_rag": "enabled"
        },
        "retrievers": {
            "hybrid_retriever": "enabled",
            "qdrant_retriever": "enabled"
        }
    }
