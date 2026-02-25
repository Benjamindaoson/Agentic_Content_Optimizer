"""
Writer Agent - 集成 Planning 和 Reflection

增强功能：
- 任务自动拆解（Planning）
- 执行结果反思（Reflection）
- 自动重试和改进
"""

from typing import Dict, Any, List, Optional
import logging
from app.engine.agents.base import BaseAgent, AgentConfig, AgentResponse
from app.engine.llm.providers.base import BaseLLMProvider
from app.ml.rl.action_space import ActionSpace
from app.engine.schemas.blueprint import GeneratedContent, TextStructure, Blueprint
from app.engine.agents.prompts.text_generation import (
    build_text_generation_prompt,
    build_blueprint_stage1_prompt,
    build_blueprint_stage2_prompt,
)
from app.engine.rag.retrievers.hybrid_retriever import HybridRetriever
from app.engine.agents.planning import Planner, Reflector, Plan, PlanStep
from app.prompting.repository import prompt_repository

logger = logging.getLogger(__name__)


class WriterAgent(BaseAgent):
    """Writer Agent V2 - 集成 Planning 和 Reflection

    新增能力：
    1. 自动任务拆解（Planning）
    2. 执行结果反思（Reflection）
    3. 基于反馈的自动重试
    4. 多候选生成和最优选择
    """

    def __init__(
        self,
        config: AgentConfig,
        llm_provider: BaseLLMProvider,
        action_space: ActionSpace,
        enable_dynamic_rag: bool = True,
        enable_planning: bool = True,
        enable_reflection: bool = True,
        max_retries: int = 2
    ):
        super().__init__(config)
        self.llm = llm_provider
        self.action_space = action_space
        self.max_retries = max_retries

        # RAG 组件
        self.enable_dynamic_rag = enable_dynamic_rag
        if enable_dynamic_rag:
            self.hybrid_retriever = HybridRetriever()
            logger.info("Writer Agent V2: Dynamic RAG enabled")

        # Planning 和 Reflection 组件
        self.enable_planning = enable_planning
        self.enable_reflection = enable_reflection

        if enable_planning:
            self.planner = Planner()
            logger.info("Writer Agent V2: Planning enabled")

        if enable_reflection:
            self.reflector = Reflector()
            logger.info("Writer Agent V2: Reflection enabled")

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """执行内容生成（带 Planning 和 Reflection）

        Args:
            input_data: {
                "action": {"hook": "H01", "body": "B01", "cta": "C01"},
                "topic": "AI 提效工具",
                "platform": "xiaohongshu",
                "goal_metric": "engagement",
                "references": [...],
                "geo_keywords": ["AI工具", "效率提升"],
                "target_audience": "25-35岁职场人士",
                "content_style": "专业、轻松"
            }

        Returns:
            AgentResponse with GeneratedContent
        """
        try:
            topic = input_data["topic"]
            platform = input_data["platform"]

            # Phase 1: Planning（如果启用）
            if self.enable_planning:
                plan = await self._create_execution_plan(input_data)
                logger.info(f"Writer Agent V2: Created plan with {len(plan.steps)} steps")
            else:
                # 使用默认计划
                plan = self._create_default_plan(input_data)

            # Phase 2: Execution with Reflection
            best_result = None
            best_score = 0.0

            for attempt in range(self.max_retries + 1):
                logger.info(f"Writer Agent V2: Attempt {attempt + 1}/{self.max_retries + 1}")

                # 执行计划中的每个步骤
                step_results = {}
                for step in plan.steps:
                    result = await self._execute_step(step, input_data, step_results)
                    step_results[step.step_id] = result

                    # Reflection（如果启用）
                    if self.enable_reflection:
                        reflection = await self.reflector.reflect(
                            goal=step.goal,
                            result=result,
                            success_criteria=step.success_criteria,
                            context={"attempt": attempt + 1, "step_id": step.step_id}
                        )

                        logger.info(
                            f"Writer Agent V2: Step {step.step_id} reflection - "
                            f"score={reflection.score}, needs_retry={reflection.needs_retry}"
                        )

                        # 如果步骤失败且还有重试机会，使用反馈重试
                        if reflection.needs_retry and attempt < self.max_retries:
                            logger.info(f"Writer Agent V2: Retrying step {step.step_id} with feedback")
                            result = await self._retry_step_with_feedback(
                                step,
                                result,
                                reflection.improvement_suggestions,
                                input_data
                            )
                            step_results[step.step_id] = result

                # 整合最终结果
                final_content = await self._integrate_results(step_results, input_data)

                # 整体 Reflection
                if self.enable_reflection:
                    final_reflection = await self.reflector.reflect(
                        goal="生成高质量病毒式内容",
                        result=final_content,
                        success_criteria="内容质量评分 >= 8.0，GEO 覆盖率 >= 0.8",
                        context={"attempt": attempt + 1, "topic": topic, "platform": platform}
                    )

                    logger.info(
                        f"Writer Agent V2: Final reflection - "
                        f"score={final_reflection.score}, needs_retry={final_reflection.needs_retry}"
                    )

                    # 保留最佳结果
                    if final_reflection.score > best_score:
                        best_score = final_reflection.score
                        best_result = final_content

                    # 如果达到标准，提前结束
                    if not final_reflection.needs_retry:
                        logger.info(f"Writer Agent V2: Quality standard met, stopping at attempt {attempt + 1}")
                        break

                    # 如果是最后一次尝试，使用最佳结果
                    if attempt == self.max_retries:
                        logger.info(f"Writer Agent V2: Max retries reached, using best result (score={best_score})")
                        final_content = best_result
                else:
                    # 没有 Reflection，直接使用当前结果
                    final_content = final_content
                    break

            return AgentResponse(
                success=True,
                data=final_content.dict() if hasattr(final_content, 'dict') else final_content,
                metadata={
                    "agent": "WriterAgentV2",
                    "planning_enabled": self.enable_planning,
                    "reflection_enabled": self.enable_reflection,
                    "attempts": attempt + 1,
                    "final_score": best_score if self.enable_reflection else None
                }
            )

        except Exception as e:
            logger.error(f"Writer Agent V2 execution failed: {e}", exc_info=True)
            return await self._handle_error(e)

    async def _create_execution_plan(self, input_data: Dict[str, Any]) -> Plan:
        """创建执行计划"""
        topic = input_data["topic"]
        platform = input_data["platform"]
        goal_metric = input_data.get("goal_metric", "engagement")

        task_description = f"为'{topic}'生成{platform}平台的病毒式内容"

        plan = await self.planner.create_plan(
            task=task_description,
            context={
                "platform": platform,
                "goal_metric": goal_metric,
                "constraints": [
                    "内容需符合平台规范",
                    "GEO 关键词覆盖率 >= 80%",
                    "文案长度适中（800-1200字）"
                ]
            },
            max_steps=5
        )

        return plan

    def _create_default_plan(self, input_data: Dict[str, Any]) -> Plan:
        """创建默认计划（不使用 LLM）"""
        from app.engine.agents.planning.planner import Plan, PlanStep

        steps = [
            PlanStep(
                step_id=1,
                goal="准备参考内容",
                action="检索和压缩参考内容",
                success_criteria="获得至少 3 个高质量参考",
                estimated_tokens=200
            ),
            PlanStep(
                step_id=2,
                goal="生成文案结构",
                action="根据策略生成 Hook + Body + CTA",
                success_criteria="文案长度 800-1200 字，包含所有 GEO 关键词",
                estimated_tokens=1000,
                dependencies=[1]
            ),
            PlanStep(
                step_id=3,
                goal="生成拍摄蓝图",
                action="基于文案生成视觉蓝图",
                success_criteria="包含至少 3 个镜头，每个镜头有明确描述",
                estimated_tokens=800,
                dependencies=[2]
            ),
            PlanStep(
                step_id=4,
                goal="计算质量指标",
                action="计算 GEO 覆盖率和其他指标",
                success_criteria="GEO 覆盖率 >= 0.8",
                estimated_tokens=100,
                dependencies=[2]
            )
        ]

        return Plan(
            task=f"生成{input_data['platform']}内容",
            steps=steps,
            total_estimated_tokens=2100,
            complexity="medium"
        )

    async def _execute_step(
        self,
        step: PlanStep,
        input_data: Dict[str, Any],
        previous_results: Dict[int, Any]
    ) -> Any:
        """执行单个计划步骤"""
        logger.info(f"Writer Agent V2: Executing step {step.step_id} - {step.goal}")

        # 根据步骤 ID 执行不同的操作
        if step.step_id == 1 or "参考" in step.goal or "检索" in step.action:
            # 步骤 1: 准备参考内容
            return await self._prepare_references(input_data)

        elif step.step_id == 2 or "文案" in step.goal or "生成" in step.action:
            # 步骤 2: 生成文案结构
            references = previous_results.get(1, input_data.get("references", []))
            return await self._generate_text_structure_step(input_data, references)

        elif step.step_id == 3 or "蓝图" in step.goal or "视觉" in step.action:
            # 步骤 3: 生成拍摄蓝图
            text_structure = previous_results.get(2)
            references = previous_results.get(1, input_data.get("references", []))
            return await self._generate_blueprint_step(input_data, text_structure, references)

        elif step.step_id == 4 or "指标" in step.goal or "计算" in step.action:
            # 步骤 4: 计算质量指标
            text_structure = previous_results.get(2)
            return await self._calculate_metrics(input_data, text_structure)

        else:
            # 默认：执行完整生成
            logger.warning(f"Writer Agent V2: Unknown step type, executing full generation")
            return await self._execute_full_generation(input_data)

    async def _prepare_references(self, input_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """准备参考内容（步骤 1）"""
        references = input_data.get("references", [])
        topic = input_data["topic"]
        platform = input_data["platform"]

        # 动态 RAG 增强
        if self.enable_dynamic_rag and len(references) < 3:
            logger.info(f"Writer Agent V2: References insufficient, performing dynamic RAG")
            additional_refs = await self._dynamic_rag_retrieval(topic, platform, limit=5)
            references.extend(additional_refs)

        # Context Compression
        if self.enable_dynamic_rag and len(references) > 5:
            references = await self._compress_references(references, limit=5)

        logger.info(f"Writer Agent V2: Prepared {len(references)} references")
        return references

    async def _generate_text_structure_step(
        self,
        input_data: Dict[str, Any],
        references: List[Dict[str, Any]]
    ) -> TextStructure:
        """生成文案结构（步骤 2）"""
        action = input_data["action"]
        topic = input_data["topic"]
        platform = input_data["platform"]
        geo_keywords = input_data.get("geo_keywords", [])
        target_audience = input_data.get("target_audience")
        content_style = input_data.get("content_style")

        # 获取策略描述
        hook_strategy = self.action_space.HOOKS.get(action["hook"], "未知策略")
        body_strategy = self.action_space.BODIES.get(action["body"], "未知策略")
        cta_strategy = self.action_space.CTAS.get(action["cta"], "未知策略")

        # 构建 Prompt（优先 DB 版本化模板，缺失时回退本地模板）
        local_prompt = build_text_generation_prompt(
            topic=topic,
            platform=platform,
            hook_strategy=hook_strategy,
            body_strategy=body_strategy,
            cta_strategy=cta_strategy,
            hook_code=action["hook"],
            body_code=action["body"],
            cta_code=action["cta"],
            geo_keywords=geo_keywords,
            references=references,
            target_audience=target_audience,
            content_style=content_style
        )
        prompt = await prompt_repository.render_prompt(
            name="text_generation",
            variables={
                "topic": topic,
                "platform": platform,
                "hook_strategy": hook_strategy,
                "body_strategy": body_strategy,
                "cta_strategy": cta_strategy,
                "hook_code": action["hook"],
                "body_code": action["body"],
                "cta_code": action["cta"],
                "geo_keywords": ", ".join(geo_keywords),
                "target_audience": target_audience or "",
                "content_style": content_style or "",
                "references": references,
            },
            channel=platform,
        ) or local_prompt

        # 使用 Structured Output，避免正则提取 JSON 的脆弱性
        messages = [{"role": "user", "content": prompt}]
        schema = TextStructure.model_json_schema()
        text_data = await self.llm.structured_output(
            messages=messages,
            schema=schema,
            temperature=0.8,
        )
        return TextStructure(**text_data)

    async def _generate_blueprint_step(
        self,
        input_data: Dict[str, Any],
        text_structure: TextStructure,
        references: List[Dict[str, Any]]
    ) -> Blueprint:
        """生成拍摄蓝图（两阶段：导演决策 → 摄影指导）"""
        topic = input_data["topic"]
        platform = input_data["platform"]

        # Stage 1: 场景 + 镜头 + 道具
        local_prompt1 = build_blueprint_stage1_prompt(
            topic=topic,
            platform=platform,
            text_structure=text_structure.full_text,
            references=references,
        )
        prompt1 = await prompt_repository.render_prompt(
            name="blueprint_stage1",
            variables={
                "topic": topic,
                "platform": platform,
                "text_structure": text_structure.full_text,
                "references": references,
            },
            channel=platform,
        ) or local_prompt1
        messages1 = [{"role": "user", "content": prompt1}]
        stage1_schema = {
            "type": "object",
            "properties": {
                "scene": {"type": "string"},
                "scene_tags": {"type": "array", "items": {"type": "string"}},
                "shot_list": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "subject": {"type": "string"},
                            "duration_s": {"type": "number"},
                            "camera_movement": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": ["type", "subject", "duration_s", "camera_movement"],
                    },
                },
                "props": {"type": "array", "items": {"type": "string"}},
                "optional_props": {"type": "array", "items": {"type": "string"}},
                "micro_innovation": {"type": "string"},
            },
            "required": ["scene", "shot_list", "props", "micro_innovation"],
        }
        stage1_data = await self.llm.structured_output(
            messages=messages1,
            schema=stage1_schema,
            temperature=0.7,
        )

        # Stage 2: 视觉风格 + 字幕 + 节奏
        local_prompt2 = build_blueprint_stage2_prompt(
            topic=topic,
            platform=platform,
            stage1_result=stage1_data,
        )
        prompt2 = await prompt_repository.render_prompt(
            name="blueprint_stage2",
            variables={
                "topic": topic,
                "platform": platform,
                "stage1_result": stage1_data,
            },
            channel=platform,
        ) or local_prompt2
        messages2 = [{"role": "user", "content": prompt2}]
        stage2_schema = {
            "type": "object",
            "properties": {
                "lighting": {"type": "string"},
                "color_tone": {"type": "string"},
                "filter_preset": {"type": "string"},
                "subtitle_style": {"type": "string"},
                "subtitle_positions": {"type": "array", "items": {"type": "string"}},
                "pacing": {"type": "string"},
                "bgm_style": {"type": "string"},
                "geo_text_overlay": {"type": "array", "items": {"type": "string"}},
                "estimated_production_time_min": {"type": "integer"},
                "difficulty_level": {"type": "string"},
            },
            "required": [
                "lighting",
                "color_tone",
                "subtitle_style",
                "subtitle_positions",
                "pacing",
                "estimated_production_time_min",
                "difficulty_level",
            ],
        }
        stage2_data = await self.llm.structured_output(
            messages=messages2,
            schema=stage2_schema,
            temperature=0.7,
        )

        # 合并两阶段结果
        blueprint_data = {**stage1_data, **stage2_data}
        return Blueprint(**blueprint_data)

    async def _calculate_metrics(
        self,
        input_data: Dict[str, Any],
        text_structure: TextStructure
    ) -> Dict[str, float]:
        """计算质量指标（步骤 4）"""
        geo_keywords = input_data.get("geo_keywords", [])

        geo_coverage = self._calculate_geo_coverage(
            text=text_structure.full_text,
            keywords=geo_keywords
        )

        return {
            "geo_coverage": geo_coverage,
            "text_length": len(text_structure.full_text)
        }

    async def _integrate_results(
        self,
        step_results: Dict[int, Any],
        input_data: Dict[str, Any]
    ) -> GeneratedContent:
        """整合所有步骤的结果"""
        text_structure = step_results.get(2)
        blueprint = step_results.get(3)
        metrics = step_results.get(4, {})

        if not text_structure:
            raise ValueError("Text structure not generated")

        if not blueprint:
            # 如果没有蓝图，生成一个默认的
            blueprint = Blueprint(
                shots=[],
                visual_style="默认风格",
                color_palette=["#FFFFFF"],
                music_suggestion="轻快背景音乐"
            )

        return GeneratedContent(
            text_structure=text_structure,
            blueprint=blueprint,
            geo_keywords=input_data.get("geo_keywords", []),
            geo_coverage=metrics.get("geo_coverage", 0.0),
            action=input_data["action"]
        )

    async def _retry_step_with_feedback(
        self,
        step: PlanStep,
        previous_result: Any,
        improvement_suggestions: List[str],
        input_data: Dict[str, Any]
    ) -> Any:
        """使用反馈重试步骤"""
        logger.info(f"Writer Agent V2: Retrying step {step.step_id} with feedback")

        # 将改进建议添加到 input_data
        enhanced_input = input_data.copy()
        enhanced_input["feedback"] = improvement_suggestions
        enhanced_input["previous_result"] = previous_result

        # 重新执行步骤
        return await self._execute_step(step, enhanced_input, {})

    async def _execute_full_generation(self, input_data: Dict[str, Any]) -> GeneratedContent:
        """执行完整生成（降级方案）"""
        # 使用原始 Writer Agent 的逻辑
        action = input_data["action"]
        topic = input_data["topic"]
        platform = input_data["platform"]
        references = input_data.get("references", [])
        geo_keywords = input_data.get("geo_keywords", [])

        # 准备参考
        if self.enable_dynamic_rag and len(references) < 3:
            rag_top_k = int(input_data.get("rag_top_k", 5) or 5)
            rag_query_expansion = bool(input_data.get("rag_query_expansion", True))
            additional_refs = await self._dynamic_rag_retrieval(
                topic,
                platform,
                limit=min(max(rag_top_k, 1), 20),
                use_query_expansion=rag_query_expansion,
                use_reranking=True,
            )
            references.extend(additional_refs)

        if self.enable_dynamic_rag and len(references) > 5 and bool(input_data.get("rag_context_compression", True)):
            references = await self._compress_references(references, limit=5)

        # 生成文案
        text_structure = await self._generate_text_structure_step(input_data, references)

        # 生成蓝图
        blueprint = await self._generate_blueprint_step(input_data, text_structure, references)

        # 计算指标
        geo_coverage = self._calculate_geo_coverage(text_structure.full_text, geo_keywords)

        return GeneratedContent(
            text_structure=text_structure,
            blueprint=blueprint,
            geo_keywords=geo_keywords,
            geo_coverage=geo_coverage,
            action=action
        )

    def _calculate_geo_coverage(self, text: str, keywords: List[str]) -> float:
        """计算 GEO 关键词覆盖率"""
        if not keywords:
            return 0.0

        covered = sum(1 for keyword in keywords if keyword in text)
        coverage = covered / len(keywords)

        return round(coverage, 2)

    async def _dynamic_rag_retrieval(
        self,
        topic: str,
        platform: str,
        limit: int = 5,
        use_query_expansion: bool = True,
        use_reranking: bool = True,
    ) -> List[Dict[str, Any]]:
        """动态 RAG 检索"""
        try:
            results = await self.hybrid_retriever.hybrid_search(
                query=topic,
                limit=limit,
                filters={"platform": platform},
                use_query_expansion=use_query_expansion,
                use_reranking=use_reranking
            )
            return results
        except Exception as e:
            logger.error(f"Dynamic RAG retrieval failed: {e}")
            return []

    async def _compress_references(
        self,
        references: List[Dict[str, Any]],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """压缩参考内容"""
        try:
            sorted_refs = sorted(
                references,
                key=lambda x: x.get("score", 0),
                reverse=True
            )
            compressed = sorted_refs[:limit]

            if hasattr(self, 'hybrid_retriever'):
                texts = [ref.get("metadata", {}).get("text", "") for ref in compressed]
                query = " ".join([ref.get("metadata", {}).get("topic", "") for ref in compressed[:2]])

                compressed_texts = await self.hybrid_retriever.context_compression(
                    documents=texts,
                    query=query
                )

                for i, ref in enumerate(compressed):
                    if i < len(compressed_texts):
                        ref["metadata"]["text"] = compressed_texts[i]

            return compressed

        except Exception as e:
            logger.error(f"Context compression failed: {e}")
            return references[:limit]
