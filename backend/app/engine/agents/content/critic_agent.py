"""
Critic Agent - 集成 Planning 和 Reflection

增强功能：
- 评估任务自动拆解（Planning）
- 评估结果反思（Reflection）
- 多维度评估的系统性保证
"""

from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from app.engine.agents.base import BaseAgent, AgentConfig, AgentResponse
from app.engine.llm.providers.base import BaseLLMProvider
from app.engine.schemas.evaluation import (
    CriticEvaluation,
    DimensionScore,
    EvaluationDimension,
    ApprovalStatus
)
from app.engine.schemas.blueprint import GeneratedContent
from app.engine.agents.prompts.critic_evaluation import build_critic_evaluation_prompt
from app.engine.rag.retrievers.hybrid_retriever import HybridRetriever
from app.engine.rag.advanced_rag import AdaptiveRAG
from app.engine.agents.planning import Planner, Reflector, Plan

logger = logging.getLogger(__name__)


class CriticAgent(BaseAgent):
    """Critic Agent V2 - 集成 Planning 和 Reflection

    新增能力：
    1. 评估维度自动规划（Planning）
    2. 评估全面性反思（Reflection）
    3. 确保评估的系统性和完整性
    """

    def __init__(
        self,
        config: AgentConfig,
        llm_provider: BaseLLMProvider,
        enable_adaptive_rag: bool = True,
        enable_planning: bool = True,
        enable_reflection: bool = True
    ):
        super().__init__(config)
        self.llm = llm_provider

        # Adaptive RAG 组件
        self.enable_adaptive_rag = enable_adaptive_rag
        if enable_adaptive_rag:
            self.adaptive_rag = AdaptiveRAG(HybridRetriever())
            logger.info("Critic Agent V2: Adaptive RAG enabled")

        # Planning 和 Reflection 组件
        self.enable_planning = enable_planning
        self.enable_reflection = enable_reflection

        if enable_planning:
            self.planner = Planner()
            logger.info("Critic Agent V2: Planning enabled")

        if enable_reflection:
            self.reflector = Reflector()
            logger.info("Critic Agent V2: Reflection enabled")

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """执行内容评估（带 Planning 和 Reflection）

        Args:
            input_data: {
                "generated_content": GeneratedContent,
                "platform": "xiaohongshu",
                "goal_metric": "engagement",
                "references": [...],
                "quality_threshold": 0.7
            }

        Returns:
            AgentResponse with CriticEvaluation
        """
        try:
            start_time = datetime.now()

            generated_content = input_data["generated_content"]
            platform = input_data["platform"]
            goal_metric = input_data.get("goal_metric", "engagement")
            references = input_data.get("references", [])
            quality_threshold = input_data.get("quality_threshold", 0.7)

            # Phase 1: Planning - 规划评估维度
            if self.enable_planning:
                evaluation_plan = await self._create_evaluation_plan(
                    platform=platform,
                    goal_metric=goal_metric,
                    content_type="viral_content"
                )
                logger.info(f"Critic Agent V2: Created evaluation plan with {len(evaluation_plan.steps)} dimensions")
            else:
                evaluation_plan = self._create_default_evaluation_plan()

            # Phase 2: 检索评估标准（Adaptive RAG）
            evaluation_criteria = []
            if self.enable_adaptive_rag:
                topic = generated_content.get("text_structure", {}).get("topic", "")
                evaluation_criteria = await self._retrieve_evaluation_criteria(
                    topic=topic,
                    platform=platform,
                    goal_metric=goal_metric
                )
                logger.info(f"Critic Agent V2: Retrieved {len(evaluation_criteria)} evaluation criteria")

            # Phase 3: 执行多维度评估
            dimension_scores = []
            for step in evaluation_plan.steps:
                score = await self._evaluate_single_dimension(
                    dimension_name=step.goal,
                    generated_content=generated_content,
                    platform=platform,
                    references=references,
                    evaluation_criteria=evaluation_criteria
                )
                dimension_scores.append(score)

                # Reflection: 验证单个维度评估的合理性
                if self.enable_reflection:
                    reflection = await self.reflector.reflect(
                        goal=f"评估{step.goal}维度",
                        result=score,
                        success_criteria=step.success_criteria,
                        context={"dimension": step.goal, "score": score.score}
                    )

                    if reflection.needs_retry:
                        logger.info(f"Critic Agent V2: Re-evaluating {step.goal} based on reflection")
                        score = await self._evaluate_single_dimension(
                            dimension_name=step.goal,
                            generated_content=generated_content,
                            platform=platform,
                            references=references,
                            evaluation_criteria=evaluation_criteria,
                            feedback=reflection.improvement_suggestions
                        )
                        dimension_scores[-1] = score

            # Phase 4: 计算综合评分
            overall_score = sum(s.score for s in dimension_scores) / len(dimension_scores)

            # Phase 5: 审批决策
            approval_status = self._make_approval_decision(
                overall_score=overall_score,
                dimension_scores=dimension_scores,
                quality_threshold=quality_threshold
            )

            # Phase 6: 生成评估摘要
            summary = await self._generate_summary(
                dimension_scores=dimension_scores,
                overall_score=overall_score,
                approval_status=approval_status
            )

            # Phase 7: 提取关键问题和亮点
            critical_issues = self._extract_critical_issues(dimension_scores)
            highlights = self._extract_highlights(dimension_scores)

            # Phase 8: 生成改进建议
            improvement_suggestions = self._generate_improvement_suggestions(
                dimension_scores=dimension_scores,
                approval_status=approval_status
            )

            # Phase 9: 整体 Reflection - 验证评估的全面性
            if self.enable_reflection:
                evaluation_result = {
                    "overall_score": overall_score,
                    "dimension_scores": [s.dict() for s in dimension_scores],
                    "approval_status": approval_status.value
                }

                overall_reflection = await self.reflector.reflect(
                    goal="完成全面的内容质量评估",
                    result=evaluation_result,
                    success_criteria="评估覆盖所有关键维度，评分合理，建议具体可行",
                    context={
                        "platform": platform,
                        "goal_metric": goal_metric,
                        "num_dimensions": len(dimension_scores)
                    }
                )

                logger.info(
                    f"Critic Agent V2: Overall reflection - "
                    f"score={overall_reflection.score}, confidence={overall_reflection.confidence}"
                )

                # 如果整体评估不够全面，添加警告
                if overall_reflection.score < 8.0:
                    critical_issues.append(
                        f"评估可能不够全面（反思评分: {overall_reflection.score}）"
                    )
                    improvement_suggestions.extend(overall_reflection.improvement_suggestions)

            # Phase 10: 组装评估结果
            evaluation_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            evaluation = CriticEvaluation(
                dimension_scores=dimension_scores,
                overall_score=round(overall_score, 2),
                approval_status=approval_status,
                summary=summary,
                critical_issues=critical_issues,
                highlights=highlights,
                improvement_suggestions=improvement_suggestions,
                evaluation_time_ms=evaluation_time_ms,
                model_version="critic-v2.0-planning-reflection"
            )

            return AgentResponse(
                success=True,
                data=evaluation.dict(),
                metadata={
                    "agent": "CriticAgentV2",
                    "overall_score": overall_score,
                    "approval_status": approval_status.value,
                    "evaluation_time_ms": evaluation_time_ms,
                    "planning_enabled": self.enable_planning,
                    "reflection_enabled": self.enable_reflection,
                    "num_dimensions": len(dimension_scores)
                }
            )

        except Exception as e:
            logger.error(f"Critic Agent V2 execution failed: {e}", exc_info=True)
            return await self._handle_error(e)

    async def _create_evaluation_plan(
        self,
        platform: str,
        goal_metric: str,
        content_type: str
    ) -> Plan:
        """创建评估计划 - 规划评估维度"""

        task_description = f"评估{platform}平台的{content_type}质量，优化{goal_metric}指标"

        plan = await self.planner.create_plan(
            task=task_description,
            context={
                "platform": platform,
                "goal_metric": goal_metric,
                "content_type": content_type,
                "constraints": [
                    "评估需要全面覆盖内容质量、用户体验、平台规范",
                    "每个维度需要有明确的评分标准",
                    "评估结果需要可操作的改进建议"
                ]
            },
            max_steps=8  # 最多 8 个评估维度
        )

        return plan

    def _create_default_evaluation_plan(self) -> Plan:
        """创建默认评估计划"""
        from app.engine.agents.planning.planner import Plan, PlanStep

        steps = [
            PlanStep(
                step_id=1,
                goal="内容质量",
                action="评估文案的原创性、深度、价值",
                success_criteria="评分客观，有具体依据",
                estimated_tokens=300
            ),
            PlanStep(
                step_id=2,
                goal="用户体验",
                action="评估可读性、吸引力、情感共鸣",
                success_criteria="评分客观，有具体依据",
                estimated_tokens=300
            ),
            PlanStep(
                step_id=3,
                goal="平台适配",
                action="评估是否符合平台规范和用户习惯",
                success_criteria="评分客观，有具体依据",
                estimated_tokens=300
            ),
            PlanStep(
                step_id=4,
                goal="SEO 优化",
                action="评估关键词覆盖、标题优化",
                success_criteria="评分客观，有具体依据",
                estimated_tokens=300
            ),
            PlanStep(
                step_id=5,
                goal="视觉呈现",
                action="评估拍摄蓝图的可行性和吸引力",
                success_criteria="评分客观，有具体依据",
                estimated_tokens=300
            )
        ]

        return Plan(
            task="内容质量评估",
            steps=steps,
            total_estimated_tokens=1500,
            complexity="medium"
        )

    async def _evaluate_single_dimension(
        self,
        dimension_name: str,
        generated_content: Dict[str, Any],
        platform: str,
        references: List[Dict[str, Any]],
        evaluation_criteria: List[Dict[str, Any]],
        feedback: Optional[List[str]] = None
    ) -> DimensionScore:
        """评估单个维度"""

        # 映射维度名称到 EvaluationDimension 枚举
        dimension_map = {
            "内容质量": EvaluationDimension.CONTENT_QUALITY,
            "用户体验": EvaluationDimension.USER_EXPERIENCE,
            "平台适配": EvaluationDimension.PLATFORM_FIT,
            "SEO 优化": EvaluationDimension.SEO_OPTIMIZATION,
            "视觉呈现": EvaluationDimension.VISUAL_APPEAL,
            "情感共鸣": EvaluationDimension.EMOTIONAL_RESONANCE,
            "行动号召": EvaluationDimension.CALL_TO_ACTION,
            "创新性": EvaluationDimension.INNOVATION
        }

        dimension = dimension_map.get(dimension_name, EvaluationDimension.CONTENT_QUALITY)

        # 构建评估 Prompt
        prompt = self._build_dimension_evaluation_prompt(
            dimension_name=dimension_name,
            generated_content=generated_content,
            platform=platform,
            references=references,
            evaluation_criteria=evaluation_criteria,
            feedback=feedback
        )

        # 调用 LLM 评估
        messages = [{"role": "user", "content": prompt}]
        response = await self.llm.chat_completion(
            messages=messages,
            temperature=0.3,  # 低温度确保评估客观
            max_tokens=500
        )

        # 解析评分和理由
        score, reasoning = self._parse_evaluation_response(response)

        return DimensionScore(
            dimension=dimension,
            score=score,
            reasoning=reasoning,
            weight=1.0
        )

    def _build_dimension_evaluation_prompt(
        self,
        dimension_name: str,
        generated_content: Dict[str, Any],
        platform: str,
        references: List[Dict[str, Any]],
        evaluation_criteria: List[Dict[str, Any]],
        feedback: Optional[List[str]] = None
    ) -> str:
        """构建维度评估 Prompt"""

        text_structure = generated_content.get("text_structure", {})
        full_text = text_structure.get("full_text", "")

        prompt = f"""你是一个专业的内容质量评估专家。请评估以下内容在"{dimension_name}"维度的表现。

**平台**: {platform}

**内容**:
{full_text[:1000]}...

**评估维度**: {dimension_name}

**评估标准**:
"""

        # 添加评估标准
        if evaluation_criteria:
            for i, criterion in enumerate(evaluation_criteria[:3], 1):
                prompt += f"{i}. {criterion.get('text', '')}\n"
        else:
            # 默认标准
            prompt += f"- 内容是否在{dimension_name}方面表现优秀\n"
            prompt += f"- 是否符合{platform}平台的最佳实践\n"
            prompt += f"- 是否有明显的改进空间\n"

        # 添加反馈（如果有）
        if feedback:
            prompt += f"\n**上次评估的改进建议**:\n"
            for suggestion in feedback:
                prompt += f"- {suggestion}\n"
            prompt += "\n请考虑这些建议重新评估。\n"

        prompt += f"""
**评分要求**:
- 给出 0-10 分的评分（8-10分为优秀，6-7分为良好，4-5分为及格，0-3分为不及格）
- 提供具体的评分理由（至少 2-3 点）
- 评分要客观、有依据

**输出格式**:
评分: X.X
理由:
1. ...
2. ...
3. ...

请开始评估:"""

        return prompt

    def _parse_evaluation_response(self, response: str) -> tuple[float, str]:
        """解析评估响应"""
        import re

        # 提取评分
        score_match = re.search(r'评分[：:]\s*(\d+\.?\d*)', response)
        if score_match:
            score = float(score_match.group(1))
        else:
            # 尝试其他格式
            score_match = re.search(r'(\d+\.?\d*)\s*分', response)
            score = float(score_match.group(1)) if score_match else 7.0

        # 确保评分在 0-10 范围内
        score = max(0.0, min(10.0, score))

        # 提取理由
        reasoning_match = re.search(r'理由[：:](.*?)(?=\n\n|\Z)', response, re.DOTALL)
        if reasoning_match:
            reasoning = reasoning_match.group(1).strip()
        else:
            reasoning = response[:500]  # 使用前 500 字符作为理由

        return score, reasoning

    def _make_approval_decision(
        self,
        overall_score: float,
        dimension_scores: List[DimensionScore],
        quality_threshold: float
    ) -> ApprovalStatus:
        """做出审批决策"""

        # 检查是否有任何维度低于 5 分（不及格）
        has_failing_dimension = any(s.score < 5.0 for s in dimension_scores)

        if has_failing_dimension:
            return ApprovalStatus.REJECTED

        if overall_score >= quality_threshold * 10:
            return ApprovalStatus.APPROVED
        elif overall_score >= (quality_threshold - 0.1) * 10:
            return ApprovalStatus.NEEDS_REVISION
        else:
            return ApprovalStatus.REJECTED

    async def _generate_summary(
        self,
        dimension_scores: List[DimensionScore],
        overall_score: float,
        approval_status: ApprovalStatus
    ) -> str:
        """生成评估摘要"""

        summary_parts = [
            f"综合评分: {overall_score:.1f}/10",
            f"审批状态: {approval_status.value}"
        ]

        # 添加各维度评分
        summary_parts.append("\n各维度评分:")
        for score in dimension_scores:
            summary_parts.append(f"- {score.dimension.value}: {score.score:.1f}/10")

        return "\n".join(summary_parts)

    def _extract_critical_issues(self, dimension_scores: List[DimensionScore]) -> List[str]:
        """提取关键问题"""
        issues = []

        for score in dimension_scores:
            if score.score < 6.0:
                issues.append(f"{score.dimension.value}评分较低({score.score:.1f}): {score.reasoning[:100]}")

        return issues

    def _extract_highlights(self, dimension_scores: List[DimensionScore]) -> List[str]:
        """提取亮点"""
        highlights = []

        for score in dimension_scores:
            if score.score >= 8.5:
                highlights.append(f"{score.dimension.value}表现优秀({score.score:.1f}): {score.reasoning[:100]}")

        return highlights

    def _generate_improvement_suggestions(
        self,
        dimension_scores: List[DimensionScore],
        approval_status: ApprovalStatus
    ) -> List[str]:
        """生成改进建议"""
        suggestions = []

        # 针对低分维度提供建议
        for score in dimension_scores:
            if score.score < 7.0:
                suggestions.append(f"改进{score.dimension.value}: {score.reasoning[:150]}")

        # 如果没有低分维度，提供通用建议
        if not suggestions and approval_status != ApprovalStatus.APPROVED:
            suggestions.append("整体质量良好，可以进一步优化细节")

        return suggestions[:5]  # 最多 5 条建议

    async def _retrieve_evaluation_criteria(
        self,
        topic: str,
        platform: str,
        goal_metric: str
    ) -> List[Dict[str, Any]]:
        """使用 Adaptive RAG 检索评估标准"""
        try:
            query = f"{platform}平台 {topic} 内容评估标准 最佳实践"

            result = await self.adaptive_rag.generate(
                query=query,
                context={"platform": platform, "goal_metric": goal_metric}
            )
            # Extract relevant documents/criteria from the generate result
            results = result.get("result", {}).get("documents", []) if isinstance(result, dict) else []

            return results
        except Exception as e:
            logger.error(f"Failed to retrieve evaluation criteria: {e}")
            return []
