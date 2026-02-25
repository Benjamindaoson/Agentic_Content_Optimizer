"""
v4.0 Growth Brain RL API 路由

提供强化学习相关的 API 端点
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

router = APIRouter(prefix="/api/v1/rl", tags=["rl"])


# ==================== 请求/响应模型 ====================

class TrainPolicyRequest(BaseModel):
    account_id: Optional[str] = None
    days: int = 7


class TrainPolicyResponse(BaseModel):
    status: str
    run_id: Optional[str] = None
    total_samples: int
    patterns_updated: int
    avg_improvement: float
    training_time: float


class SelectTopicsRequest(BaseModel):
    account_id: str
    k: int = 3
    exploration_rate: float = 0.2


class SelectGeneratorRequest(BaseModel):
    generators: List[str]
    style: str
    account_id: str


class SelectPlatformsRequest(BaseModel):
    content_id: str
    available_platforms: List[str]
    k: int = 3


class CausalPolicyRequest(BaseModel):
    graph_id: str
    treatment_variable: str
    outcome_variable: str


# ==================== Auto Account Manager RL ====================

@router.post("/account/train", response_model=TrainPolicyResponse)
async def train_account_policy(
    request: TrainPolicyRequest,
    db: Session = Depends(get_db)
):
    """
    训练账号运营策略 (GRPO)

    使用历史数据训练话题选择和排程策略
    """
    rl_manager = AutoAccountManager(db, enable_rag=False, enable_rl=True)

    result = await rl_manager.train_policy(
        account_id=request.account_id,
        days=request.days
    )

    if result['status'] != 'success':
        raise HTTPException(status_code=400, detail=result)

    return TrainPolicyResponse(**result)


@router.post("/account/select-topics")
async def select_topics_with_rl(
    request: SelectTopicsRequest,
    db: Session = Depends(get_db)
):
    """
    使用 Thompson Sampling 选择话题

    探索-利用平衡的话题选择
    """
    rl_manager = AutoAccountManager(db, enable_rag=False, enable_rl=True)

    # 获取候选话题
    from app.engine.growth_brain.auto_account_manager import DiscoveredTopic, TopicStatus
    from sqlalchemy import and_
    from datetime import datetime, timedelta

    cutoff_time = datetime.now() - timedelta(hours=24)
    topics = db.query(DiscoveredTopic).filter(
        and_(
            DiscoveredTopic.discovered_at >= cutoff_time,
            DiscoveredTopic.status == TopicStatus.DISCOVERED
        )
    ).all()

    selected = await rl_manager.select_topics_with_thompson_sampling(
        account_id=request.account_id,
        candidate_topics=topics,
        k=request.k,
        exploration_rate=request.exploration_rate
    )

    return {
        'status': 'success',
        'selected_topics': [
            {
                'topic_id': t.topic_id,
                'topic_name': t.topic_name,
                'heat_score': t.heat_score
            }
            for t in selected
        ]
    }


@router.get("/account/evaluate")
async def evaluate_account_policy(
    days: int = 7,
    db: Session = Depends(get_db)
):
    """
    评估账号运营策略准确性

    返回预测 vs 实际的准确性指标
    """
    rl_manager = AutoAccountManager(db, enable_rag=False, enable_rl=True)

    report = await rl_manager.evaluate_accuracy(days=days)

    return report


# ==================== Multimodal Cover Engine RL ====================

@router.post("/cover/select-generator")
async def select_generator_with_rl(
    request: SelectGeneratorRequest,
    db: Session = Depends(get_db)
):
    """
    使用 Thompson Sampling 选择封面生成器

    自动选择最优的生成器 (DALL-E, SD, Midjourney)
    """
    rl_manager = MultimodalCoverEngine(db, enable_rag=False, enable_rl=True)

    generator = await rl_manager.select_generator_with_thompson_sampling(
        generators=request.generators,
        style=request.style,
        account_id=request.account_id
    )

    return {
        'status': 'success',
        'selected_generator': generator
    }


@router.post("/cover/optimize-ab-test")
async def optimize_cover_ab_test(
    test_id: str,
    cover_variants: List[str],
    db: Session = Depends(get_db)
):
    """
    优化封面 A/B 测试 (Multi-Armed Bandit)

    动态分配流量到表现最好的封面
    """
    rl_manager = MultimodalCoverEngine(db, enable_rag=False, enable_rl=True)

    result = await rl_manager.optimize_ab_test(
        test_id=test_id,
        cover_variants=cover_variants
    )

    return result


@router.post("/cover/train")
async def train_cover_policy(
    days: int = 7,
    db: Session = Depends(get_db)
):
    """
    训练封面生成策略

    学习最优的生成器、风格、参数组合
    """
    rl_manager = MultimodalCoverEngine(db, enable_rag=False, enable_rl=True)

    result = await rl_manager.train_cover_policy(days=days)

    return result


# ==================== Multi Platform Engine RL ====================

@router.post("/platform/select-platforms")
async def select_platforms_with_rl(
    request: SelectPlatformsRequest,
    db: Session = Depends(get_db)
):
    """
    使用 Thompson Sampling 选择发布平台

    自动选择最优的平台组合
    """
    rl_manager = MultiPlatformEngine(db, enable_rag=False, enable_rl=True)

    platforms = await rl_manager.select_platforms_with_thompson_sampling(
        content_id=request.content_id,
        available_platforms=request.available_platforms,
        k=request.k
    )

    return {
        'status': 'success',
        'selected_platforms': platforms
    }


@router.post("/platform/optimize-adaptation")
async def optimize_platform_adaptation(
    content_id: str,
    platform: str,
    db: Session = Depends(get_db)
):
    """
    优化平台适配策略

    学习每个平台的最佳实践
    """
    rl_manager = MultiPlatformEngine(db, enable_rag=False, enable_rl=True)

    result = await rl_manager.optimize_platform_adaptation(
        content_id=content_id,
        platform=platform
    )

    return result


@router.post("/platform/train")
async def train_platform_policy(
    days: int = 7,
    db: Session = Depends(get_db)
):
    """
    训练平台选择策略

    学习最优的平台组合和适配方式
    """
    rl_manager = MultiPlatformEngine(db, enable_rag=False, enable_rl=True)

    result = await rl_manager.train_platform_policy(days=days)

    return result


# ==================== Causal Inference Engine RL ====================

@router.post("/causal/optimize-policy")
async def causal_policy_optimization(
    request: CausalPolicyRequest,
    db: Session = Depends(get_db)
):
    """
    因果策略优化

    使用因果图指导策略学习
    """
    rl_manager = CausalInferenceEngine(db, enable_rag=False, enable_rl=True)

    result = await rl_manager.causal_policy_optimization(
        graph_id=request.graph_id,
        treatment_variable=request.treatment_variable,
        outcome_variable=request.outcome_variable
    )

    return result


@router.get("/causal/evaluate-counterfactual")
async def evaluate_counterfactual_policy(
    scenario_id: str,
    db: Session = Depends(get_db)
):
    """
    反事实策略评估

    评估"如果采取不同策略会怎样"
    """
    rl_manager = CausalInferenceEngine(db, enable_rag=False, enable_rl=True)

    result = await rl_manager.counterfactual_policy_evaluation(
        scenario_id=scenario_id
    )

    return result


@router.post("/causal/train")
async def train_causal_aware_policy(
    graph_id: str,
    days: int = 7,
    db: Session = Depends(get_db)
):
    """
    训练因果感知策略

    结合因果图和 RL 训练
    """
    rl_manager = CausalInferenceEngine(db, enable_rag=False, enable_rl=True)

    result = await rl_manager.train_causal_aware_policy(
        graph_id=graph_id,
        days=days
    )

    return result


# ==================== 通用 RL 端点 ====================

@router.get("/status")
async def get_rl_status(db: Session = Depends(get_db)):
    """
    获取 RL 系统状态

    返回所有 RL 组件的状态
    """
    return {
        'status': 'operational',
        'components': {
            'auto_account_manager': 'enabled',
            'multimodal_cover_engine': 'enabled',
            'multi_platform_engine': 'enabled',
            'causal_inference_engine': 'enabled'
        },
        'algorithms': {
            'thompson_sampling': 'enabled',
            'grpo': 'enabled',
            'ppo': 'available',
            'diversity_scorer': 'enabled'
        }
    }


@router.post("/train-all")
async def train_all_policies(
    days: int = 7,
    db: Session = Depends(get_db)
):
    """
    训练所有策略

    一键训练所有 RL 组件
    """
    results = {}

    # 1. 训练账号运营策略
    account_rl = AutoAccountManager(db, enable_rag=False, enable_rl=True)
    results['account'] = await account_rl.train_policy(days=days)

    # 2. 训练封面策略
    cover_rl = MultimodalCoverEngine(db, enable_rag=False, enable_rl=True)
    results['cover'] = await cover_rl.train_cover_policy(days=days)

    # 3. 训练平台策略
    platform_rl = MultiPlatformEngine(db, enable_rag=False, enable_rl=True)
    results['platform'] = await platform_rl.train_platform_policy(days=days)

    return {
        'status': 'success',
        'results': results
    }
