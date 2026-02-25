"""
LangGraph 工作流 - Agent 编排

实现 Trend → Writer → Critic 的完整工作流
"""

from typing import TypedDict, Annotated, Sequence, Literal, Optional, Tuple
import operator
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import logging
import time
from datetime import datetime
import random

from app.shared.websocket.manager import manager as ws_manager
from app.engine.llm.cost_router import get_llm_params
from app.engine.llm.token_counter import estimate_tokens
from app.ml.rl.action_space import action_space as _action_space
from app.ml.rl.contextual_bandit import ContextFeatures
from app.ml.rl.contextual_persistence import load_contextual_bandit, save_contextual_bandit
from app.ml.rl.thompson_sampling import ThompsonSamplingConfig
from app.ml.rl.thompson_persistence import load_selector, update_action
from app.monitoring import get_production_monitor

logger = logging.getLogger(__name__)


class ContentGenerationState(TypedDict):
    """内容生成工作流状态"""
    # 输入
    topic: str
    platform: str
    goal_metric: str
    target_audience: str
    content_style: str

    # 中间结果
    trend_analysis: dict
    references: list
    selected_action: dict
    policy_id: str
    generated_content: dict
    evaluation: dict

    # 控制流
    iteration: int
    max_iterations: int

    # 历史记录
    messages: Annotated[Sequence[dict], operator.add]

    # 最终结果
    final_content: dict
    final_score: float

    # 封面生成
    cover_candidates: list

    # Token 预算控制
    token_budget_remaining: int

    # 运行时配置（来自 API）
    runtime_config: dict


class ContentGenerationWorkflow:
    """内容生成工作流

    工作流图:
    START → Trend Analysis → Content Generation → Content Evaluation
                                      ↑                    ↓
                                      └─── Refinement ←───┘
                                                ↓
                                              END
    """

    def __init__(
        self,
        trend_agent,
        writer_agent,
        critic_agent,
        max_iterations: int = 3,
        quality_threshold: float = 8.0
    ):
        """初始化工作流

        Args:
            trend_agent: Trend Agent 实例
            writer_agent: Writer Agent 实例（建议使用 V2）
            critic_agent: Critic Agent 实例（建议使用 V2）
            max_iterations: 最大迭代次数
            quality_threshold: 质量阈值（0-10）
        """
        self.trend_agent = trend_agent
        self.writer_agent = writer_agent
        self.critic_agent = critic_agent
        self.max_iterations = max_iterations
        self.quality_threshold = quality_threshold

        # 构建工作流图
        self.workflow = self._build_workflow()

        # 添加内存检查点（用于状态持久化）
        self.memory = MemorySaver()
        self.app = self.workflow.compile(checkpointer=self.memory)

        logger.info("ContentGenerationWorkflow initialized")

    async def _push_workflow_status(
        self,
        node: str,
        status: str,
        duration_ms: Optional[int] = None,
        summary: Optional[str] = None,
        token_usage: Optional[dict] = None,
        extra: Optional[dict] = None
    ) -> None:
        """广播工作流节点状态，供前端实时可视化使用。"""
        payload = {
            "type": "workflow_status",
            "node": node,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
        if duration_ms is not None:
            payload["duration_ms"] = duration_ms
        if summary is not None:
            payload["summary"] = summary
        if token_usage is not None:
            payload["token_usage"] = token_usage
        if extra:
            payload.update(extra)

        # 优先推送到 workflow 频道（前端可订阅），同时广播给全部连接做兜底
        await ws_manager.broadcast_to_channel("workflow", payload)
        await ws_manager.broadcast(payload)

    def _build_workflow(self) -> StateGraph:
        """构建工作流图"""
        workflow = StateGraph(ContentGenerationState)

        # 添加节点
        workflow.add_node("route_start", self._route_start_node)
        workflow.add_node("trend_analysis", self._trend_analysis_node)
        workflow.add_node("director_sample", self._director_node)
        workflow.add_node("content_generation", self._content_generation_node)
        workflow.add_node("content_evaluation", self._content_evaluation_node)
        workflow.add_node("refinement", self._refinement_node)
        workflow.add_node("cover_generation", self._cover_generation_node)

        # 设置入口点
        workflow.set_entry_point("route_start")

        # 添加边
        workflow.add_conditional_edges(
            "route_start",
            self._route_start,
            {
                "trend_analysis": "trend_analysis",
                "content_generation": "content_generation",
            },
        )

        workflow.add_edge("trend_analysis", "director_sample")
        workflow.add_edge("director_sample", "content_generation")

        workflow.add_conditional_edges(
            "content_generation",
            self._route_after_generation,
            {
                "content_evaluation": "content_evaluation",
                "end": END,
            },
        )

        # 添加条件边：根据评估结果决定是否重新生成
        workflow.add_conditional_edges(
            "content_evaluation",
            self._should_refine,
            {
                "refine": "refinement",
                "cover": "cover_generation",
                "end": END
            }
        )

        # 改进后重新生成
        workflow.add_edge("refinement", "content_generation")
        workflow.add_edge("cover_generation", END)

        return workflow

    def _get_agent_mode(self, state: ContentGenerationState) -> str:
        rc = state.get("runtime_config", {}) or {}
        agent = (rc.get("agent") or {}) if isinstance(rc, dict) else {}
        mode = agent.get("mode") if isinstance(agent, dict) else None
        return str(mode or "full_pipeline")

    async def _route_start_node(self, state: ContentGenerationState) -> ContentGenerationState:
        # 仅用于动态切图，避免硬编码执行路径
        return state

    def _route_start(self, state: ContentGenerationState) -> Literal["trend_analysis", "content_generation"]:
        mode = self._get_agent_mode(state)
        if mode == "full_pipeline":
            return "trend_analysis"
        return "content_generation"

    def _route_after_generation(self, state: ContentGenerationState) -> Literal["content_evaluation", "end"]:
        mode = self._get_agent_mode(state)
        if mode == "writer_only":
            # writer_only: 生成即结束
            state["final_content"] = state.get("generated_content", {}) or {}
            state["final_score"] = state.get("final_score", 0.0) or 0.0
            return "end"
        return "content_evaluation"

    def _action_code_lists(self) -> Tuple[list[str], list[str], list[str]]:
        hooks = list(_action_space.HOOKS.keys())
        bodies = list(_action_space.BODIES.keys())
        ctas = list(_action_space.CTAS.keys())
        return hooks, bodies, ctas

    def _action_to_idx(self, hook: str, body: str, cta: str) -> Tuple[int, int, int]:
        hooks, bodies, ctas = self._action_code_lists()
        h = hooks.index(hook) if hook in hooks else 0
        b = bodies.index(body) if body in bodies else 0
        c = ctas.index(cta) if cta in ctas else 0
        return (h, b, c)

    def _idx_to_action(self, h: int, b: int, c: int) -> Tuple[str, str, str]:
        hooks, bodies, ctas = self._action_code_lists()
        return (
            hooks[max(0, min(h, len(hooks) - 1))],
            bodies[max(0, min(b, len(bodies) - 1))],
            ctas[max(0, min(c, len(ctas) - 1))],
        )

    def _default_action(self) -> Tuple[str, str, str]:
        return ("H01", "B01", "C01")

    def _policy_id(self, hook: str, body: str, cta: str) -> str:
        return f"{hook}-{body}-{cta}"

    def _idx_to_flat(self, idx: Tuple[int, int, int]) -> int:
        _, bodies, ctas = self._action_code_lists()
        h, b, c = idx
        return h * len(bodies) * len(ctas) + b * len(ctas) + c

    def _flat_to_idx(self, flat: int) -> Tuple[int, int, int]:
        hooks, bodies, ctas = self._action_code_lists()
        n_b, n_c = len(bodies), len(ctas)
        h = flat // (n_b * n_c)
        rem = flat % (n_b * n_c)
        b = rem // n_c
        c = rem % n_c
        return (
            max(0, min(h, len(hooks) - 1)),
            max(0, min(b, len(bodies) - 1)),
            max(0, min(c, len(ctas) - 1)),
        )

    def _build_context_features(self, state: ContentGenerationState) -> ContextFeatures:
        now = datetime.utcnow()
        topic = str(state.get("topic", ""))
        style = str(state.get("content_style", ""))
        if len(topic) <= 20:
            length = "short"
        elif len(topic) <= 60:
            length = "medium"
        else:
            length = "long"
        return ContextFeatures(
            topic_category=topic,
            platform=str(state.get("platform", "xiaohongshu")),
            hour_of_day=now.hour,
            day_of_week=now.weekday(),
            audience_type=str(state.get("target_audience", "")),
            content_length=length,
        )

    async def _select_action(self, state: ContentGenerationState) -> Tuple[str, str, str]:
        rc = state.get("runtime_config", {}) or {}
        rl = (rc.get("rl") or {}) if isinstance(rc, dict) else {}
        gen = (rc.get("generation") or {}) if isinstance(rc, dict) else {}

        hooks, bodies, ctas = self._action_code_lists()
        hook, body, cta = self._default_action()

        th_enabled = bool(rl.get("thompson_sampling_enabled", True))
        contextual_enabled = bool(rl.get("contextual_bandit_enabled", True))
        epsilon = float(rl.get("exploration_rate", 0.1) or 0.0)

        if th_enabled:
            user_id_raw = rc.get("user_id")
            user_id = int(user_id_raw) if user_id_raw is not None else 0

            selector = await load_selector(
                user_id=user_id,
                n_hooks=len(hooks),
                n_bodies=len(bodies),
                n_ctas=len(ctas),
                config=ThompsonSamplingConfig(use_hierarchical=True, temperature=1.0, min_pulls=3),
            )
            h_i = b_i = c_i = 0
            if contextual_enabled:
                total_actions = len(hooks) * len(bodies) * len(ctas)
                bandit = await load_contextual_bandit(user_id=user_id, n_actions=total_actions)
                context = self._build_context_features(state)
                # 数据冷启动阶段仍走 TS；足够数据后切 LinUCB
                if bandit.total_pulls >= 100:
                    flat_action, _ = bandit.select_action(context)
                    h_i, b_i, c_i = self._flat_to_idx(flat_action)
                elif random.random() < epsilon:
                    h_i = random.randint(0, len(hooks) - 1)
                    b_i = random.randint(0, len(bodies) - 1)
                    c_i = random.randint(0, len(ctas) - 1)
                else:
                    h_i, b_i, c_i = selector.select_action(mode="auto")
            else:
                if random.random() < epsilon:
                    h_i = random.randint(0, len(hooks) - 1)
                    b_i = random.randint(0, len(bodies) - 1)
                    c_i = random.randint(0, len(ctas) - 1)
                else:
                    h_i, b_i, c_i = selector.select_action(mode="auto")

            hook, body, cta = self._idx_to_action(h_i, b_i, c_i)
        else:
            hook, body, cta = _action_space.sample_action()

        # generation 开关：允许固定某些维度（用于灰度/实验）
        if not bool(gen.get("enable_hook_strategy", True)):
            hook = self._default_action()[0]
        if not bool(gen.get("enable_cta_strategy", True)):
            cta = self._default_action()[2]

        return hook, body, cta

    def _apply_selected_action(self, state: ContentGenerationState, hook: str, body: str, cta: str) -> None:
        policy_id = self._policy_id(hook, body, cta)
        state["policy_id"] = policy_id
        state["selected_action"] = {
            "hook": hook,
            "body": body,
            "cta": cta,
            "hook_name": _action_space.get_action_name(hook),
            "body_name": _action_space.get_action_name(body),
            "cta_name": _action_space.get_action_name(cta),
            "idx": self._action_to_idx(hook, body, cta),
        }

    async def _director_node(self, state: ContentGenerationState) -> ContentGenerationState:
        """策略采样节点（Director）

        目标：让 RL 开关真实生效：按 Thompson Sampling/探索率采样 action，并把 policy_id 写入 state。
        """
        started = time.time()
        await self._push_workflow_status(node="director_sample", status="running")

        try:
            hook, body, cta = await self._select_action(state)
            self._apply_selected_action(state, hook, body, cta)
            policy_id = state.get("policy_id")

            await self._push_workflow_status(
                node="director_sample",
                status="done",
                duration_ms=int((time.time() - started) * 1000),
                summary=f"policy={policy_id}",
                extra={"output": {"policy_id": policy_id, "action": state["selected_action"]}},
            )
        except Exception as e:
            logger.error(f"[Director] Error: {e}", exc_info=True)
            hook, body, cta = self._default_action()
            self._apply_selected_action(state, hook, body, cta)
            await self._push_workflow_status(
                node="director_sample",
                status="error",
                duration_ms=int((time.time() - started) * 1000),
                summary=str(e),
            )

        return state

    async def _trend_analysis_node(self, state: ContentGenerationState) -> ContentGenerationState:
        """趋势分析节点

        使用 Trend Agent 分析当前趋势并检索参考内容
        """
        logger.info(f"[Trend Analysis] Topic: {state['topic']}, Platform: {state['platform']}")
        started = time.time()
        await self._push_workflow_status(
            node="trend_analysis",
            status="running",
            extra={
                "input": {
                    "topic": state.get("topic"),
                    "platform": state.get("platform")
                }
            }
        )

        try:
            rc = state.get("runtime_config", {}) or {}
            rag = (rc.get("rag") or {}) if isinstance(rc, dict) else {}

            # 调用 Trend Agent
            result = await self.trend_agent.execute({
                "topic": state["topic"],
                "platform": state["platform"],
                "goal_metric": state.get("goal_metric", "engagement"),
                "limit": rag.get("top_k", 10),
                "rag_mode": rag.get("mode", "adaptive"),
                "rag_hybrid_search": rag.get("hybrid_search", True),
                "rag_query_expansion": rag.get("query_expansion", True),
                "quality_threshold": 0.6,
            })

            if result.success:
                trend_data = result.data

                # 更新状态
                state["trend_analysis"] = trend_data.get("trend_analysis", {})
                state["references"] = trend_data.get("references", [])

                # 添加消息
                state["messages"] = state.get("messages", []) + [{
                    "role": "trend_agent",
                    "content": f"Found {len(state['references'])} references",
                    "data": trend_data
                }]

                logger.info(f"[Trend Analysis] Success: {len(state['references'])} references found")
                await self._push_workflow_status(
                    node="trend_analysis",
                    status="done",
                    duration_ms=int((time.time() - started) * 1000),
                    summary=f"Found {len(state['references'])} references",
                    extra={
                        "output": {
                            "reference_count": len(state.get("references", [])),
                            "trend_analysis": state.get("trend_analysis", {})
                        }
                    }
                )
            else:
                logger.error(f"[Trend Analysis] Failed: {result.metadata}")
                state["references"] = []
                await self._push_workflow_status(
                    node="trend_analysis",
                    status="error",
                    duration_ms=int((time.time() - started) * 1000),
                    summary="Trend analysis failed"
                )

        except Exception as e:
            logger.error(f"[Trend Analysis] Error: {e}", exc_info=True)
            state["references"] = []
            await self._push_workflow_status(
                node="trend_analysis",
                status="error",
                duration_ms=int((time.time() - started) * 1000),
                summary=str(e)
            )

        return state

    async def _content_generation_node(self, state: ContentGenerationState) -> ContentGenerationState:
        """内容生成节点

        使用 Writer Agent 生成内容
        """
        budget = state.get("token_budget_remaining", 30000)
        if budget <= 0:
            logger.warning("[Budget] Token budget exhausted, skipping generation")
            return state

        iteration = state.get("iteration", 0)
        logger.info(f"[Content Generation] Iteration {iteration + 1}/{state.get('max_iterations', 3)}")
        started = time.time()
        await self._push_workflow_status(
            node="content_generation",
            status="running",
            extra={
                "input": {
                    "topic": state.get("topic"),
                    "platform": state.get("platform"),
                    "iteration": iteration + 1
                }
            }
        )

        try:
            rc = state.get("runtime_config", {}) or {}
            rag = (rc.get("rag") or {}) if isinstance(rc, dict) else {}

            # writer_only / writer_critic 路径没有显式 director 节点，这里兜底采样一次
            if not state.get("selected_action"):
                try:
                    hook, body, cta = await self._select_action(state)
                    self._apply_selected_action(state, hook, body, cta)
                except Exception:
                    hook, body, cta = self._default_action()
                    self._apply_selected_action(state, hook, body, cta)

            action = state.get("selected_action") or {}
            action_payload = {
                "hook": action.get("hook") or self._default_action()[0],
                "body": action.get("body") or self._default_action()[1],
                "cta": action.get("cta") or self._default_action()[2],
            }
            policy_id = state.get("policy_id") or self._policy_id(action_payload["hook"], action_payload["body"], action_payload["cta"])

            # 准备输入数据
            input_data = {
                "action": action_payload,
                "topic": state["topic"],
                "platform": state["platform"],
                "references": state.get("references", []),
                "geo_keywords": self._extract_keywords(state),
                "target_audience": state.get("target_audience"),
                "content_style": state.get("content_style"),
                "policy_id": policy_id,
                # RAG runtime
                "rag_top_k": rag.get("top_k", 5),
                "rag_query_expansion": rag.get("query_expansion", True),
                "rag_context_compression": rag.get("context_compression", True),
            }

            # 如果有评估反馈，添加到输入
            if "evaluation" in state and state["evaluation"]:
                input_data["feedback"] = state["evaluation"].get("improvement_suggestions", [])

            # 调用 Writer Agent（前后分别计量 token）
            input_tokens = estimate_tokens(input_data)
            result = await self.writer_agent.execute(input_data)

            if result.success:
                # 将策略信息附着到内容上，便于 trace / dashboard 统计
                content = result.data or {}
                content["action"] = action_payload
                content["policy_id"] = policy_id
                state["generated_content"] = content

                # 添加消息
                state["messages"] = state.get("messages", []) + [{
                    "role": "writer_agent",
                    "content": "Content generated",
                    "iteration": iteration + 1,
                    "data": result.data
                }]

                output_tokens = estimate_tokens(content)
                total_tokens = input_tokens + output_tokens
                state["token_budget_remaining"] = max(
                    state.get("token_budget_remaining", 30000) - total_tokens,
                    0,
                )
                content["token_usage"] = {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "budget_remaining": state["token_budget_remaining"],
                }

                logger.info(f"[Content Generation] Success at iteration {iteration + 1}")
                await self._push_workflow_status(
                    node="content_generation",
                    status="done",
                    duration_ms=int((time.time() - started) * 1000),
                    summary=f"Generated content at iteration {iteration + 1}",
                    token_usage=content.get("token_usage"),
                    extra={
                        "output": {
                            "title": content.get("title"),
                            "iteration": iteration + 1,
                            "policy_id": policy_id,
                        }
                    }
                )
            else:
                logger.error(f"[Content Generation] Failed: {result.metadata}")
                await self._push_workflow_status(
                    node="content_generation",
                    status="error",
                    duration_ms=int((time.time() - started) * 1000),
                    summary="Content generation failed"
                )

        except Exception as e:
            logger.error(f"[Content Generation] Error: {e}", exc_info=True)
            await self._push_workflow_status(
                node="content_generation",
                status="error",
                duration_ms=int((time.time() - started) * 1000),
                summary=str(e)
            )

        return state

    async def _content_evaluation_node(self, state: ContentGenerationState) -> ContentGenerationState:
        """内容评估节点

        使用 Critic Agent 评估内容质量
        """
        logger.info("[Content Evaluation] Evaluating generated content")
        started = time.time()
        await self._push_workflow_status(
            node="content_evaluation",
            status="running",
            extra={
                "input": {
                    "platform": state.get("platform"),
                    "quality_threshold": self.quality_threshold
                }
            }
        )

        try:
            # 调用 Critic Agent
            result = await self.critic_agent.execute({
                "generated_content": state.get("generated_content", {}),
                "platform": state["platform"],
                "goal_metric": state.get("goal_metric", "engagement"),
                "references": state.get("references", []),
                "quality_threshold": self.quality_threshold / 10  # 转换为 0-1 范围
            })

            if result.success:
                evaluation = result.data
                state["evaluation"] = evaluation

                overall_score = evaluation.get("overall_score", 0)
                approval_status = evaluation.get("approval_status", "REJECTED")
                policy_id = (state.get("generated_content") or {}).get("policy_id") or state.get("policy_id")

                # 添加消息
                state["messages"] = state.get("messages", []) + [{
                    "role": "critic_agent",
                    "content": f"Evaluation complete: {overall_score}/10, Status: {approval_status}",
                    "data": evaluation
                }]

                logger.info(f"[Content Evaluation] Score: {overall_score}/10, Status: {approval_status}")
                await self._push_workflow_status(
                    node="content_evaluation",
                    status="done",
                    duration_ms=int((time.time() - started) * 1000),
                    summary=f"Score {overall_score}/10 ({approval_status})",
                    token_usage=evaluation.get("token_usage"),
                    extra={
                        "output": {
                            "overall_score": overall_score,
                            "approval_status": approval_status,
                            "improvement_suggestions": evaluation.get("improvement_suggestions", []),
                            "policy_id": policy_id,
                        }
                    }
                )

                # 在线更新 Thompson Sampling（把本轮评估转成 reward）
                try:
                    rc = state.get("runtime_config", {}) or {}
                    rl = (rc.get("rl") or {}) if isinstance(rc, dict) else {}
                    if bool(rl.get("thompson_sampling_enabled", True)):
                        user_id_raw = rc.get("user_id")
                        user_id = int(user_id_raw) if user_id_raw is not None else 0
                        action_obj = state.get("selected_action") or {}
                        idx = action_obj.get("idx")
                        if isinstance(idx, (list, tuple)) and len(idx) == 3:
                            # Critic 自评仅作初始信号（×0.3），真实 Outcome 通过
                            # outcome_reward_bridge 以完整权重回灌
                            raw = max(0.0, min(float(overall_score) / 10.0, 1.0))
                            reward = raw * 0.3
                            # 轻微惩罚被拒绝的结果，逼近“更像成功概率”的口径
                            if str(approval_status).lower().startswith("reject"):
                                reward = reward * 0.5

                            hooks, bodies, ctas = self._action_code_lists()
                            selector = await load_selector(
                                user_id=user_id,
                                n_hooks=len(hooks),
                                n_bodies=len(bodies),
                                n_ctas=len(ctas),
                                config=ThompsonSamplingConfig(use_hierarchical=True, temperature=1.0, min_pulls=3),
                            )
                            await update_action(
                                user_id=user_id,
                                selector=selector,
                                action=(int(idx[0]), int(idx[1]), int(idx[2])),
                                reward=reward,
                            )
                            if bool(rl.get("contextual_bandit_enabled", True)):
                                total_actions = len(hooks) * len(bodies) * len(ctas)
                                bandit = await load_contextual_bandit(
                                    user_id=user_id,
                                    n_actions=total_actions,
                                )
                                ctx = self._build_context_features(state)
                                bandit.update(self._idx_to_flat((int(idx[0]), int(idx[1]), int(idx[2]))), ctx, reward)
                                await save_contextual_bandit(user_id=user_id, bandit=bandit)
                except Exception as e:
                    logger.warning(f"[RL] Thompson update skipped: {e}")

                # 如果是最佳结果，保存
                if overall_score > state.get("final_score", 0):
                    state["final_content"] = state["generated_content"]
                    state["final_score"] = overall_score

                # 生产监控记录 + 告警派发
                try:
                    monitor = get_production_monitor()
                    action_obj = state.get("selected_action") or {}
                    strategy = (
                        action_obj.get("hook", "H01"),
                        action_obj.get("body", "B01"),
                        action_obj.get("cta", "C01"),
                    )
                    total_reward = max(0.0, min(float(overall_score) / 10.0, 1.0))
                    monitor.record_generation(
                        similarity=0.0,  # 由去重模块可替换真实相似度
                        strategy=strategy,
                        reward_components={
                            "quality": total_reward,
                            "total": total_reward,
                        },
                        is_new_action=False,
                    )
                    dispatch = monitor.dispatch_alerts(total_possible_actions=400)
                    if dispatch.get("alerts"):
                        logger.warning(f"[Monitor] Alerts dispatched: {dispatch}")
                except Exception as mon_err:
                    logger.warning(f"[Monitor] record/dispatch skipped: {mon_err}")
            else:
                logger.error(f"[Content Evaluation] Failed: {result.metadata}")
                await self._push_workflow_status(
                    node="content_evaluation",
                    status="error",
                    duration_ms=int((time.time() - started) * 1000),
                    summary="Content evaluation failed"
                )

        except Exception as e:
            logger.error(f"[Content Evaluation] Error: {e}", exc_info=True)
            await self._push_workflow_status(
                node="content_evaluation",
                status="error",
                duration_ms=int((time.time() - started) * 1000),
                summary=str(e)
            )

        return state

    async def _refinement_node(self, state: ContentGenerationState) -> ContentGenerationState:
        """改进节点

        分析评估反馈，准备下一次迭代
        """
        logger.info("[Refinement] Analyzing feedback for next iteration")
        started = time.time()
        await self._push_workflow_status(
            node="refinement",
            status="running",
            extra={
                "input": {
                    "iteration": state.get("iteration", 0),
                    "max_iterations": state.get("max_iterations", self.max_iterations)
                }
            }
        )

        # 增加迭代计数
        state["iteration"] = state.get("iteration", 0) + 1

        # 提取改进建议
        evaluation = state.get("evaluation", {})
        improvement_suggestions = evaluation.get("improvement_suggestions", [])
        critical_issues = evaluation.get("critical_issues", [])

        # 添加消息
        state["messages"] = state.get("messages", []) + [{
            "role": "refinement",
            "content": f"Iteration {state['iteration']} complete, preparing for retry",
            "suggestions": improvement_suggestions,
            "issues": critical_issues
        }]

        logger.info(f"[Refinement] Iteration {state['iteration']}, {len(improvement_suggestions)} suggestions")
        await self._push_workflow_status(
            node="refinement",
            status="done",
            duration_ms=int((time.time() - started) * 1000),
            summary=f"{len(improvement_suggestions)} suggestions for next iteration",
            extra={
                "output": {
                    "iteration": state.get("iteration"),
                    "critical_issues": critical_issues,
                    "improvement_suggestions": improvement_suggestions
                }
            }
        )

        return state

    def _should_refine(self, state: ContentGenerationState) -> Literal["refine", "cover", "end"]:
        """判断是否需要改进

        决策逻辑:
        1. 如果评分 >= 阈值 → 检查是否要生成封面
        2. 如果达到最大迭代次数 → 结束（或生成封面）
        3. 否则，继续改进
        """
        evaluation = state.get("evaluation", {})
        overall_score = evaluation.get("overall_score", 0)
        iteration = state.get("iteration", 0)
        max_iterations = state.get("max_iterations", self.max_iterations)

        rc = state.get("runtime_config", {}) or {}
        auto_cover = bool((rc.get("cover") or {}).get("auto_generate", False))

        # writer_only：不走 refinement 循环
        if self._get_agent_mode(state) == "writer_only":
            return "cover" if auto_cover else "end"

        # 质量达标 → 进入封面生成或结束
        if overall_score >= self.quality_threshold:
            logger.info(f"[Decision] Quality threshold met ({overall_score} >= {self.quality_threshold})")
            return "cover" if auto_cover else "end"

        # 迭代次数用完 → 结束
        if iteration >= max_iterations:
            logger.info(f"[Decision] Max iterations reached ({iteration}/{max_iterations})")
            return "cover" if auto_cover else "end"

        # 继续改进
        logger.info(f"[Decision] Score {overall_score} < {self.quality_threshold}, refining (iteration {iteration}/{max_iterations})")
        return "refine"

    async def _cover_generation_node(self, state: ContentGenerationState) -> ContentGenerationState:
        """封面生成节点（可选，由 runtime_config.cover.auto_generate 控制）

        使用 DALL-E 3 根据文案内容自动生成封面候选。
        运营人员在前端手动选择最终封面。
        """
        started = time.time()
        await self._push_workflow_status(node="cover_generation", status="running")

        try:
            content = state.get("final_content") or state.get("generated_content") or {}
            title = content.get("title", state.get("topic", ""))
            hook = content.get("hook", "")

            from app.engine.llm.unified import UnifiedLLM
            llm = UnifiedLLM()

            cover_prompt = await llm.chat(
                messages=[{"role": "user", "content": (
                    f"为以下小红书笔记生成一段英文封面图片描述（用于 AI 生图）：\n"
                    f"标题：{title}\nHook：{hook}\n\n"
                    f"要求：色彩鲜明，符合小红书审美，不要包含文字。"
                    f"直接输出英文描述，不要解释。"
                )}],
                **get_llm_params("cover_prompt"),
            )

            from app.engine.growth_brain.multimodal_cover_engine import (
                MultimodalCoverEngine, CoverStyle, CoverGenerator
            )
            engine = MultimodalCoverEngine.__new__(MultimodalCoverEngine)
            candidates = await engine._generate_with_dalle(
                prompt=cover_prompt,
                style=CoverStyle.VIBRANT,
            )

            state["cover_candidates"] = [
                {"cover_id": c.cover_id, "image_path": c.image_path, "prompt": cover_prompt[:200]}
                for c in candidates
            ]

            await self._push_workflow_status(
                node="cover_generation", status="done",
                duration_ms=int((time.time() - started) * 1000),
                summary=f"Generated {len(candidates)} cover candidates",
                extra={"output": {"count": len(candidates)}},
            )
        except Exception as e:
            logger.error(f"[Cover Generation] Error: {e}", exc_info=True)
            state["cover_candidates"] = []
            await self._push_workflow_status(
                node="cover_generation", status="error",
                duration_ms=int((time.time() - started) * 1000),
                summary=str(e),
            )

        return state

    def _extract_keywords(self, state: ContentGenerationState) -> list:
        """从趋势分析中提取关键词"""
        trend_analysis = state.get("trend_analysis", {})
        keywords = trend_analysis.get("keywords", [])

        # 如果没有关键词，使用 topic
        if not keywords:
            keywords = [state["topic"]]

        return keywords[:10]  # 最多 10 个关键词

    async def run(
        self,
        topic: str,
        platform: str,
        goal_metric: str = "engagement",
        target_audience: str = None,
        content_style: str = None,
        max_iterations: int = None,
        runtime_config: Optional[dict] = None
    ) -> dict:
        """运行工作流

        Args:
            topic: 内容主题
            platform: 平台（xiaohongshu, weibo, douyin）
            goal_metric: 目标指标（engagement, conversion, awareness）
            target_audience: 目标受众
            content_style: 内容风格
            max_iterations: 最大迭代次数（覆盖默认值）

        Returns:
            dict: 工作流执行结果
        """
        logger.info(f"[Workflow] Starting: topic={topic}, platform={platform}")

        # 初始化状态
        initial_state = ContentGenerationState(
            topic=topic,
            platform=platform,
            goal_metric=goal_metric,
            target_audience=target_audience or "通用受众",
            content_style=content_style or "专业、友好",
            trend_analysis={},
            references=[],
            selected_action={},
            policy_id="",
            generated_content={},
            evaluation={},
            iteration=0,
            max_iterations=max_iterations or self.max_iterations,
            messages=[],
            final_content={},
            final_score=0.0,
            cover_candidates=[],
            token_budget_remaining=30000,
            runtime_config=runtime_config or {}
        )

        # 运行工作流
        try:
            # 使用 ainvoke 异步执行
            final_state = await self.app.ainvoke(
                initial_state,
                config={"configurable": {"thread_id": f"{topic}_{platform}"}}
            )

            # 提取结果
            result = {
                "success": True,
                "final_content": final_state.get("final_content", {}),
                "final_score": final_state.get("final_score", 0.0),
                "evaluation": final_state.get("evaluation", {}),
                "iterations": final_state.get("iteration", 0),
                "messages": final_state.get("messages", []),
                "metadata": {
                    "topic": topic,
                    "platform": platform,
                    "goal_metric": goal_metric,
                    "max_iterations": final_state.get("max_iterations", self.max_iterations),
                    "references": final_state.get("references", []),
                    "policy_id": final_state.get("policy_id"),
                    "selected_action": final_state.get("selected_action"),
                }
            }

            logger.info(
                f"[Workflow] Complete: score={result['final_score']}, "
                f"iterations={result['iterations']}"
            )

            return result

        except Exception as e:
            logger.error(f"[Workflow] Error: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "final_content": {},
                "final_score": 0.0
            }

    async def stream(
        self,
        topic: str,
        platform: str,
        goal_metric: str = "engagement",
        target_audience: str = None,
        content_style: str = None,
        max_iterations: int = None,
        runtime_config: Optional[dict] = None
    ):
        """流式运行工作流（用于实时进度展示）

        Yields:
            dict: 每个节点的执行结果
        """
        logger.info(f"[Workflow Stream] Starting: topic={topic}, platform={platform}")

        # 初始化状态
        initial_state = ContentGenerationState(
            topic=topic,
            platform=platform,
            goal_metric=goal_metric,
            target_audience=target_audience or "通用受众",
            content_style=content_style or "专业、友好",
            trend_analysis={},
            references=[],
            selected_action={},
            policy_id="",
            generated_content={},
            evaluation={},
            iteration=0,
            max_iterations=max_iterations or self.max_iterations,
            messages=[],
            final_content={},
            final_score=0.0,
            cover_candidates=[],
            token_budget_remaining=30000,
            runtime_config=runtime_config or {}
        )

        # 流式执行
        try:
            async for event in self.app.astream(
                initial_state,
                config={"configurable": {"thread_id": f"{topic}_{platform}_stream"}}
            ):
                # 每个事件包含节点名称和状态更新
                for node_name, state_update in event.items():
                    yield {
                        "node": node_name,
                        "state": state_update,
                        "timestamp": logger.handlers[0].formatter.formatTime(
                            logger.makeRecord(
                                logger.name, 0, "", 0, "", (), None
                            )
                        ) if logger.handlers else None
                    }

        except Exception as e:
            logger.error(f"[Workflow Stream] Error: {e}", exc_info=True)
            yield {
                "node": "error",
                "error": str(e),
                "state": {}
            }
