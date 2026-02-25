"""
Planner - Agent 任务规划器

实现任务拆解和执行计划生成
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.engine.llm.unified import UnifiedLLM
import logging

logger = logging.getLogger(__name__)


class PlanStep(BaseModel):
    """计划步骤"""
    step_id: int = Field(..., description="步骤 ID")
    goal: str = Field(..., description="步骤目标")
    action: str = Field(..., description="执行动作")
    required_info: List[str] = Field(default_factory=list, description="所需信息")
    success_criteria: str = Field(..., description="成功标准")
    estimated_tokens: int = Field(default=500, description="预估 token 消耗")
    dependencies: List[int] = Field(default_factory=list, description="依赖的步骤 ID")


class Plan(BaseModel):
    """执行计划"""
    task: str = Field(..., description="任务描述")
    steps: List[PlanStep] = Field(..., description="执行步骤")
    total_estimated_tokens: int = Field(default=0, description="总预估 token")
    complexity: str = Field(default="medium", description="任务复杂度: simple/medium/complex")


class Planner:
    """任务规划器

    使用 LLM 将复杂任务拆解为可执行的步骤序列
    """

    def __init__(self, llm: Optional[UnifiedLLM] = None):
        self.llm = llm or UnifiedLLM()

    async def create_plan(
        self,
        task: str,
        context: Dict[str, Any],
        max_steps: int = 5
    ) -> Plan:
        """创建执行计划

        Args:
            task: 任务描述
            context: 任务上下文（平台、目标、约束等）
            max_steps: 最大步骤数

        Returns:
            Plan: 执行计划
        """
        logger.info(f"Creating plan for task: {task}")

        # 构建 Planning Prompt
        prompt = self._build_planning_prompt(task, context, max_steps)

        # 调用 LLM 生成计划
        response = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            provider="claude",
            model="sonnet-4.5",
            temperature=0.3,  # 低温度确保计划稳定
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "execution_plan",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "complexity": {
                                "type": "string",
                                "enum": ["simple", "medium", "complex"]
                            },
                            "steps": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "step_id": {"type": "integer"},
                                        "goal": {"type": "string"},
                                        "action": {"type": "string"},
                                        "required_info": {
                                            "type": "array",
                                            "items": {"type": "string"}
                                        },
                                        "success_criteria": {"type": "string"},
                                        "estimated_tokens": {"type": "integer"},
                                        "dependencies": {
                                            "type": "array",
                                            "items": {"type": "integer"}
                                        }
                                    },
                                    "required": ["step_id", "goal", "action", "success_criteria"]
                                }
                            }
                        },
                        "required": ["complexity", "steps"]
                    }
                }
            }
        )

        # 解析响应
        plan_data = response

        # 验证计划可执行性
        validated_plan = self._validate_plan(plan_data, task)

        logger.info(f"Plan created with {len(validated_plan.steps)} steps")
        return validated_plan

    def _build_planning_prompt(
        self,
        task: str,
        context: Dict[str, Any],
        max_steps: int
    ) -> str:
        """构建 Planning Prompt"""

        platform = context.get("platform", "xiaohongshu")
        goal_metric = context.get("goal_metric", "engagement")
        constraints = context.get("constraints", [])

        prompt = f"""你是一个专业的任务规划专家。请将以下任务拆解为 {max_steps} 个以内的可执行步骤。

**任务**: {task}

**上下文**:
- 平台: {platform}
- 目标指标: {goal_metric}
- 约束条件: {', '.join(constraints) if constraints else '无'}

**要求**:
1. 每个步骤必须有明确的目标和成功标准
2. 步骤之间要有清晰的依赖关系
3. 估算每个步骤的 token 消耗
4. 确保步骤可执行且可验证

**输出格式**:
{{
    "complexity": "simple|medium|complex",
    "steps": [
        {{
            "step_id": 1,
            "goal": "明确的步骤目标",
            "action": "具体的执行动作（如：检索参考内容、生成文案结构、评估质量）",
            "required_info": ["所需的信息1", "所需的信息2"],
            "success_criteria": "可量化的成功标准（如：检索到至少3个相关案例、文案长度在800-1200字）",
            "estimated_tokens": 500,
            "dependencies": []
        }}
    ]
}}

请开始规划:"""

        return prompt

    def _validate_plan(self, plan_data: Dict[str, Any], task: str) -> Plan:
        """验证计划可执行性

        检查:
        1. 步骤 ID 连续性
        2. 依赖关系合理性
        3. 成功标准可验证性
        """
        steps = []
        total_tokens = 0

        for step_data in plan_data.get("steps", []):
            # 验证依赖关系
            dependencies = step_data.get("dependencies", [])
            for dep_id in dependencies:
                if dep_id >= step_data["step_id"]:
                    logger.warning(f"Invalid dependency: step {step_data['step_id']} depends on future step {dep_id}")
                    step_data["dependencies"] = [d for d in dependencies if d < step_data["step_id"]]

            step = PlanStep(**step_data)
            steps.append(step)
            total_tokens += step.estimated_tokens

        # 如果没有步骤，创建默认计划
        if not steps:
            logger.warning("No steps in plan, creating default plan")
            steps = [
                PlanStep(
                    step_id=1,
                    goal="完成任务",
                    action="直接执行任务",
                    success_criteria="任务完成",
                    estimated_tokens=1000
                )
            ]
            total_tokens = 1000

        return Plan(
            task=task,
            steps=steps,
            total_estimated_tokens=total_tokens,
            complexity=plan_data.get("complexity", "medium")
        )

    async def replan(
        self,
        original_plan: Plan,
        failed_step: PlanStep,
        failure_reason: str
    ) -> Plan:
        """重新规划

        当某个步骤失败时，调整计划
        """
        logger.info(f"Replanning due to failure at step {failed_step.step_id}: {failure_reason}")

        prompt = f"""原计划在执行步骤 {failed_step.step_id} 时失败。

**原步骤**:
- 目标: {failed_step.goal}
- 动作: {failed_step.action}
- 失败原因: {failure_reason}

**剩余步骤**: {len(original_plan.steps) - failed_step.step_id}

请调整计划，提供替代方案或修正步骤。输出格式与之前相同。"""

        response = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            provider="claude",
            model="haiku-4.5",  # 使用更快的模型
            temperature=0.5
        )

        # 解析并验证新计划
        new_plan_data = response
        return self._validate_plan(new_plan_data, original_plan.task)
