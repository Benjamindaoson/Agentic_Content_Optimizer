"""
API V5 - LangGraph 工作流集成

使用 LangGraph 编排 Agent 工作流
"""

import logging
import time
import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import uuid

from app.engine.agents.workflow import ContentGenerationWorkflow
from app.ml.integration.content_generation_logger import log_generation_trace
from app.engine.agents.content.trend_agent import TrendAgent
from app.engine.agents.content.writer_agent import WriterAgent
from app.engine.agents.content.critic_agent import CriticAgent
from app.engine.agents.base import AgentConfig
from app.engine.llm.providers.unified_adapter import UnifiedLLMProviderAdapter
from app.ml.rl.action_space import ActionSpace
from app.api.deps import get_current_active_user
from app.api.deps import get_current_admin_user
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/workflow", tags=["workflow"])


class WorkflowGenerateRequest(BaseModel):
    """工作流生成请求"""
    topic: str = Field(..., description="内容主题")
    request_id: Optional[str] = Field(default=None, description="可选：用于取消/追踪的请求 ID")
    platform: str = Field(default="xiaohongshu", description="平台: xiaohongshu, douyin, tiktok, kuaishou")
    goal_metric: str = Field(default="engagement", description="目标指标")
    target_audience: Optional[str] = Field(None, description="目标受众")
    content_style: Optional[str] = Field(None, description="内容风格")
    max_iterations: Optional[int] = Field(None, description="旧版字段：最大迭代次数")
    quality_threshold: Optional[float] = Field(default=75.0, description="质量阈值 (0-100)")

    # RAG 配置
    rag_mode: str = "adaptive"
    rag_hybrid_search: bool = True
    rag_top_k: int = Field(default=10, ge=1, le=20)
    rag_query_expansion: bool = True
    rag_context_compression: bool = True
    rag_trend_quality_filter: bool = True

    # RL 配置
    thompson_sampling_enabled: bool = True
    grpo_enabled: bool = False
    reward_preset: str = "balanced"
    custom_reward_weights: Optional[Dict[str, float]] = None
    exploration_rate: float = Field(default=0.1, ge=0.0, le=1.0)

    # Agent 配置
    agent_mode: str = "full_pipeline"  # full_pipeline | writer_critic | writer_only
    max_refinement_loops: int = Field(default=3, ge=1, le=5)
    human_review_enabled: bool = False

    # LLM 配置
    llm_provider: str = "claude"
    llm_model: str = "claude-sonnet-4-5-20250514"
    temperature: float = Field(default=0.7, ge=0.0, le=1.5)
    max_tokens: int = Field(default=4096, ge=128, le=8192)
    enable_model_router: bool = False
    enable_gray_release: bool = False

    # 训练配置
    sft_enabled: bool = False
    dpo_enabled: bool = False
    auto_train_on_feedback: bool = False
    feedback_threshold: int = Field(default=100, ge=1, le=10000)

    # 内容配置
    enable_geo_keywords: bool = True
    enable_hook_strategy: bool = True
    enable_cta_strategy: bool = True


class WorkflowGenerateResponse(BaseModel):
    """工作流生成响应"""
    success: bool
    final_content: dict
    final_score: float
    evaluation: dict
    iterations: int
    messages: list
    metadata: dict
    trace_id: Optional[str] = None


from app.engine.runtime_config import (
    RuntimeConfig,
    RagRuntimeConfig,
    LLMRuntimeConfig,
    RlRuntimeConfig,
    AgentRuntimeConfig,
    GenerationRuntimeConfig,
)

# ========= 保护：并发/速率/超时 =========
_GEN_SEMAPHORE = asyncio.Semaphore(4)  # 全局并发上限
_RATE_LIMIT: Dict[str, list[float]] = {}  # user_id -> timestamps (sec)
_RATE_LOCK = asyncio.Lock()
_RATE_WINDOW_S = 60
_RATE_MAX_REQ_PER_WINDOW = 10
_GEN_TIMEOUT_S = 120
_RUNNING: Dict[str, Dict[str, Any]] = {}  # request_id -> {task, user_id, started_at}
_RUNNING_LOCK = asyncio.Lock()


def create_workflow(request: WorkflowGenerateRequest) -> ContentGenerationWorkflow:
    """为本次请求创建工作流实例（避免并发下串配置）。"""
    llm_provider = UnifiedLLMProviderAdapter(
        provider=request.llm_provider,
        model=request.llm_model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
    )

    trend_agent = TrendAgent(
        config=AgentConfig(name="TrendAgent", version="1.0"),
        llm_provider=llm_provider,
        use_quality_filter=bool(request.rag_trend_quality_filter),
        enable_crag=(request.rag_mode == "crag"),
    )

    writer_agent = WriterAgent(
        config=AgentConfig(name="WriterAgent", version="2.0"),
        llm_provider=llm_provider,
        action_space=ActionSpace(),
        enable_dynamic_rag=True,
        enable_planning=True,
        enable_reflection=True,
        max_retries=2,
    )

    critic_agent = CriticAgent(
        config=AgentConfig(name="CriticAgent", version="2.0"),
        llm_provider=llm_provider,
        enable_adaptive_rag=True,
        enable_planning=True,
        enable_reflection=True,
    )

    return ContentGenerationWorkflow(
        trend_agent=trend_agent,
        writer_agent=writer_agent,
        critic_agent=critic_agent,
        max_iterations=3,
        quality_threshold=8.0,
    )


def _resolve_execution_config(request: WorkflowGenerateRequest) -> Dict[str, Any]:
    """将前端配置映射到工作流执行参数（保持向后兼容）。"""
    max_loops = request.max_iterations if request.max_iterations is not None else request.max_refinement_loops
    max_loops = max(1, min(max_loops, 5))

    quality_0_100 = request.quality_threshold if request.quality_threshold is not None else 75.0
    quality_0_100 = max(0.0, min(quality_0_100, 100.0))
    quality_0_10 = quality_0_100 / 10.0

    # writer_only 场景下尽量在首轮结束
    if request.agent_mode == "writer_only":
        quality_0_10 = 0.0
        max_loops = 1
    elif request.agent_mode == "writer_critic":
        max_loops = min(max_loops, 3)

    return {
        "max_loops": max_loops,
        "quality_0_10": quality_0_10,
        "quality_0_100": quality_0_100,
    }


def _config_snapshot(request: WorkflowGenerateRequest) -> Dict[str, Any]:
    return {
        "rag": {
            "mode": request.rag_mode,
            "hybrid_search": request.rag_hybrid_search,
            "top_k": request.rag_top_k,
            "query_expansion": request.rag_query_expansion,
            "context_compression": request.rag_context_compression,
            "trend_quality_filter": request.rag_trend_quality_filter,
        },
        "rl": {
            "thompson_sampling_enabled": request.thompson_sampling_enabled,
            "grpo_enabled": request.grpo_enabled,
            "reward_preset": request.reward_preset,
            "custom_reward_weights": request.custom_reward_weights,
            "exploration_rate": request.exploration_rate,
        },
        "agent": {
            "mode": request.agent_mode,
            "max_refinement_loops": request.max_refinement_loops,
            "quality_threshold": request.quality_threshold,
            "human_review_enabled": request.human_review_enabled,
        },
        "llm": {
            "provider": request.llm_provider,
            "model": request.llm_model,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "enable_model_router": request.enable_model_router,
            "enable_gray_release": request.enable_gray_release,
        },
        "training": {
            "sft_enabled": request.sft_enabled,
            "dpo_enabled": request.dpo_enabled,
            "auto_train_on_feedback": request.auto_train_on_feedback,
            "feedback_threshold": request.feedback_threshold,
        },
        "generation": {
            "enable_geo_keywords": request.enable_geo_keywords,
            "enable_hook_strategy": request.enable_hook_strategy,
            "enable_cta_strategy": request.enable_cta_strategy,
        },
    }


def _effective_config_keys(request: WorkflowGenerateRequest) -> Dict[str, Any]:
    """明确告知前端：哪些配置当前已生效，哪些仅记录。"""
    applied = [
        "topic",
        "platform",
        "goal_metric",
        "target_audience",
        "content_style",
        "agent_mode",
        "max_refinement_loops",
        "quality_threshold",
        # RAG (已接入到 Trend/Writer 的检索行为)
        "rag_mode",
        "rag_hybrid_search",
        "rag_top_k",
        "rag_query_expansion",
        "rag_context_compression",
        "rag_trend_quality_filter",
        # LLM (已接入到 Agent 调用)
        "llm_provider",
        "llm_model",
        "temperature",
        "max_tokens",
        # RL (已接入到 Director 策略采样 + 在线更新)
        "thompson_sampling_enabled",
        "exploration_rate",
    ]
    # 部分 RAG 细粒度参数当前未贯穿到各 Agent 实现里，这里先标记为记录
    recorded_only = [
        "grpo_enabled",
        "reward_preset",
        "custom_reward_weights",
        "enable_model_router",
        "enable_gray_release",
        "sft_enabled",
        "dpo_enabled",
        "auto_train_on_feedback",
        "feedback_threshold",
        "enable_geo_keywords",
        "enable_hook_strategy",
        "enable_cta_strategy",
    ]
    return {"applied": applied, "recorded_only": recorded_only}


async def _check_rate_limit(user: User) -> None:
    now = time.time()
    key = str(user.id)
    async with _RATE_LOCK:
        arr = _RATE_LIMIT.get(key, [])
        arr = [t for t in arr if now - t <= _RATE_WINDOW_S]
        if len(arr) >= _RATE_MAX_REQ_PER_WINDOW:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="请求过于频繁，请稍后再试",
            )
        arr.append(now)
        _RATE_LIMIT[key] = arr


async def _register_task(request_id: str, user: User, task: asyncio.Task) -> None:
    async with _RUNNING_LOCK:
        _RUNNING[request_id] = {"task": task, "user_id": str(user.id), "started_at": time.time()}


async def _unregister_task(request_id: str) -> None:
    async with _RUNNING_LOCK:
        _RUNNING.pop(request_id, None)


@router.post("/cancel/{request_id}")
async def cancel_generation(
    request_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """取消正在运行的生成任务（同用户权限校验）。"""
    async with _RUNNING_LOCK:
        entry = _RUNNING.get(request_id)
        if not entry:
            return {"success": False, "message": "未找到正在运行的任务"}
        if entry.get("user_id") != str(current_user.id) and current_user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="权限不足")
        task: asyncio.Task = entry["task"]
        task.cancel()
        return {"success": True, "message": "已发送取消请求"}


@router.post("/generate", response_model=WorkflowGenerateResponse)
@router.post("/generate/content", response_model=WorkflowGenerateResponse)
async def generate_content_with_workflow(
    request: WorkflowGenerateRequest,
    current_user: User = Depends(get_current_active_user),
):
    """使用 LangGraph 工作流生成内容

    工作流:
    1. Trend Analysis: 分析趋势，检索参考内容
    2. Content Generation: 生成内容（带 Planning 和 Reflection）
    3. Content Evaluation: 评估内容质量
    4. Refinement: 如果质量不达标，改进并重新生成（最多 3 次）

    特点:
    - 自动任务拆解（Planning）
    - 执行结果反思（Reflection）
    - 自动重试和改进
    - 状态持久化
    """
    try:
        logger.info(
            "Workflow generation request: topic=%s, platform=%s, agent_mode=%s, rag_mode=%s",
            request.topic,
            request.platform,
            request.agent_mode,
            request.rag_mode,
        )

        await _check_rate_limit(current_user)

        request_id = request.request_id or str(uuid.uuid4())

        async with _GEN_SEMAPHORE:
            # 获取工作流实例
            workflow = create_workflow(request)
            execution = _resolve_execution_config(request)
            workflow.max_iterations = execution["max_loops"]
            workflow.quality_threshold = execution["quality_0_10"]

            # 运行工作流（带超时）
            start_time = time.time()
            task: Optional[asyncio.Task] = None
            try:
                task = asyncio.create_task(
                    workflow.run(
                        topic=request.topic,
                        platform=request.platform,
                        goal_metric=request.goal_metric,
                        target_audience=request.target_audience,
                        content_style=request.content_style,
                        max_iterations=execution["max_loops"],
                        runtime_config=RuntimeConfig(
                            request_id=request_id,
                            user_id=str(current_user.id),
                            rag=RagRuntimeConfig(
                                mode=request.rag_mode,
                                hybrid_search=request.rag_hybrid_search,
                                top_k=request.rag_top_k,
                                query_expansion=request.rag_query_expansion,
                                context_compression=request.rag_context_compression,
                                trend_quality_filter=request.rag_trend_quality_filter,
                            ),
                            llm=LLMRuntimeConfig(
                                provider=request.llm_provider,
                                model=request.llm_model,
                                temperature=request.temperature,
                                max_tokens=request.max_tokens,
                            ),
                            rl=RlRuntimeConfig(
                                thompson_sampling_enabled=bool(request.thompson_sampling_enabled),
                                exploration_rate=float(request.exploration_rate),
                                reward_preset=str(request.reward_preset),
                                custom_reward_weights=request.custom_reward_weights,
                            ),
                            agent=AgentRuntimeConfig(
                                mode=str(request.agent_mode),
                                max_refinement_loops=int(request.max_refinement_loops),
                                quality_threshold_0_100=float(request.quality_threshold or 75.0),
                                human_review_enabled=bool(request.human_review_enabled),
                            ),
                            generation=GenerationRuntimeConfig(
                                enable_geo_keywords=bool(request.enable_geo_keywords),
                                enable_hook_strategy=bool(request.enable_hook_strategy),
                                enable_cta_strategy=bool(request.enable_cta_strategy),
                            ),
                            extra={},
                        ).to_dict(),
                    )
                )
                await _register_task(request_id, current_user, task)
                result = await asyncio.wait_for(task, timeout=_GEN_TIMEOUT_S)
            except asyncio.TimeoutError:
                if task is not None:
                    try:
                        task.cancel()
                    except Exception:
                        pass
                raise HTTPException(status_code=504, detail="生成超时，请缩短话题或稍后重试")
            except asyncio.CancelledError:
                raise HTTPException(status_code=499, detail="生成已取消")
            finally:
                await _unregister_task(request_id)

            generation_time_ms = int((time.time() - start_time) * 1000)

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Workflow execution failed: {result.get('error', 'Unknown error')}"
            )

        logger.info(
            f"Workflow generation complete: score={result['final_score']}, "
            f"iterations={result['iterations']}"
        )

        # 记录 trace 并返回 trace_id
        trace_id = None
        final_content = result.get("final_content", {})
        if final_content:
            trace_id = log_generation_trace(
                platform=request.platform,
                topic=request.topic,
                category="",
                target_audience=request.target_audience or "",
                style_preference=request.content_style or "",
                generated_content=final_content,
                generation_time_ms=generation_time_ms,
                model_id=request.llm_provider,
                quality_score=result.get("final_score", 0.0),
                predicted_score=result.get("final_score", 0.0),
                policy_id=final_content.get("policy_id") if isinstance(final_content, dict) else None,
                constraints={
                    "user_id": current_user.id,
                    "request_id": request_id,
                    "effective": _effective_config_keys(request),
                    "config": _config_snapshot(request),
                },
                retrieved_context=result.get("metadata", {}).get("references") if isinstance(result.get("metadata"), dict) else None,
            )
        result["trace_id"] = trace_id
        result["metadata"] = {
            **(result.get("metadata") or {}),
            "config": _config_snapshot(request),
            "execution": execution,
            "effective": _effective_config_keys(request),
            "user": {"id": current_user.id, "role": str(current_user.role)},
            "request_id": request_id,
        }

        return WorkflowGenerateResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Workflow generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/content/stream")
async def generate_content_with_workflow_stream(
    request: WorkflowGenerateRequest,
    current_user: User = Depends(get_current_active_user),
):
    """流式生成内容（实时进度）

    返回 Server-Sent Events (SSE) 流，最终事件包含 trace_id
    """
    from fastapi.responses import StreamingResponse
    import json

    async def event_generator():
        last_state = {}
        try:
            await _check_rate_limit(current_user)
            workflow = create_workflow(request)
            execution = _resolve_execution_config(request)
            workflow.max_iterations = execution["max_loops"]
            workflow.quality_threshold = execution["quality_0_10"]
            start_time = time.time()

            async with _GEN_SEMAPHORE:
                async for event in workflow.stream(
                    topic=request.topic,
                    platform=request.platform,
                    goal_metric=request.goal_metric,
                    target_audience=request.target_audience,
                    content_style=request.content_style,
                    max_iterations=execution["max_loops"],
                    runtime_config=RuntimeConfig(
                        request_id=request.request_id or "stream",
                        user_id=str(current_user.id),
                        rag=RagRuntimeConfig(
                            mode=request.rag_mode,
                            hybrid_search=request.rag_hybrid_search,
                            top_k=request.rag_top_k,
                            query_expansion=request.rag_query_expansion,
                            context_compression=request.rag_context_compression,
                            trend_quality_filter=request.rag_trend_quality_filter,
                        ),
                        llm=LLMRuntimeConfig(
                            provider=request.llm_provider,
                            model=request.llm_model,
                            temperature=request.temperature,
                            max_tokens=request.max_tokens,
                        ),
                        rl=RlRuntimeConfig(
                            thompson_sampling_enabled=bool(request.thompson_sampling_enabled),
                            exploration_rate=float(request.exploration_rate),
                            reward_preset=str(request.reward_preset),
                            custom_reward_weights=request.custom_reward_weights,
                        ),
                        agent=AgentRuntimeConfig(
                            mode=str(request.agent_mode),
                            max_refinement_loops=int(request.max_refinement_loops),
                            quality_threshold_0_100=float(request.quality_threshold or 75.0),
                            human_review_enabled=bool(request.human_review_enabled),
                        ),
                        generation=GenerationRuntimeConfig(
                            enable_geo_keywords=bool(request.enable_geo_keywords),
                            enable_hook_strategy=bool(request.enable_hook_strategy),
                            enable_cta_strategy=bool(request.enable_cta_strategy),
                        ),
                        extra={},
                    ).to_dict(),
                ):
                    state = event.get("state", {})
                    if state:
                        last_state = state
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            # 流结束后记录 trace
            final_content = last_state.get("final_content", {})
            if final_content:
                generation_time_ms = int((time.time() - start_time) * 1000)
                trace_id = log_generation_trace(
                    platform=request.platform,
                    topic=request.topic,
                    category="",
                    target_audience=request.target_audience or "",
                    style_preference=request.content_style or "",
                    generated_content=final_content,
                    generation_time_ms=generation_time_ms,
                    model_id="claude",
                    quality_score=last_state.get("final_score", 0.0),
                    predicted_score=last_state.get("final_score", 0.0),
                    policy_id=final_content.get("policy_id") if isinstance(final_content, dict) else None,
                )
                if trace_id:
                    yield f"data: {json.dumps({'trace_id': trace_id, 'type': 'complete', 'execution': execution}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


@router.get("/workflow/status")
async def get_workflow_status(
    current_user: User = Depends(get_current_active_user),
):
    """获取工作流状态"""
    return {
        "initialized": True,
        "max_iterations": None,
        "quality_threshold": None,
        "note": "当前工作流按请求构建（request-scoped），无全局单例状态"
    }


@router.post("/workflow/reset")
async def reset_workflow(
    current_user: User = Depends(get_current_admin_user),
):
    """重置工作流实例"""
    logger.info("Workflow reset requested (noop in request-scoped mode)")
    return {"success": True, "message": "noop (request-scoped mode)"}
