"""
测试 Planning 和 Reflection 模块
"""

import pytest
import asyncio
from app.agents.planning import Planner, Reflector, Plan, PlanStep, Reflection


class TestPlanner:
    """测试 Planner 类"""

    @pytest.mark.asyncio
    async def test_create_plan_basic(self):
        """测试基础计划创建"""
        planner = Planner()

        plan = await planner.create_plan(
            task="生成小红书爆款内容",
            context={
                "platform": "xiaohongshu",
                "goal_metric": "engagement"
            },
            max_steps=5
        )

        assert isinstance(plan, Plan)
        assert len(plan.steps) > 0
        assert len(plan.steps) <= 5
        assert plan.complexity in ["simple", "medium", "complex"]

    @pytest.mark.asyncio
    async def test_plan_steps_have_dependencies(self):
        """测试计划步骤的依赖关系"""
        planner = Planner()

        plan = await planner.create_plan(
            task="完成复杂的内容生成任务",
            context={"platform": "xiaohongshu"},
            max_steps=4
        )

        # 检查依赖关系的合理性
        for step in plan.steps:
            for dep_id in step.dependencies:
                assert dep_id < step.step_id, f"Step {step.step_id} depends on future step {dep_id}"

    @pytest.mark.asyncio
    async def test_plan_has_success_criteria(self):
        """测试计划步骤有成功标准"""
        planner = Planner()

        plan = await planner.create_plan(
            task="生成高质量内容",
            context={"platform": "xiaohongshu"},
            max_steps=3
        )

        for step in plan.steps:
            assert step.success_criteria, f"Step {step.step_id} missing success criteria"
            assert len(step.success_criteria) > 10, "Success criteria too short"

    @pytest.mark.asyncio
    async def test_replan_after_failure(self):
        """测试失败后重新规划"""
        planner = Planner()

        original_plan = await planner.create_plan(
            task="生成内容",
            context={"platform": "xiaohongshu"},
            max_steps=3
        )

        failed_step = original_plan.steps[1]

        new_plan = await planner.replan(
            original_plan=original_plan,
            failed_step=failed_step,
            failure_reason="LLM 生成的内容不符合平台规范"
        )

        assert isinstance(new_plan, Plan)
        assert len(new_plan.steps) > 0


class TestReflector:
    """测试 Reflector 类"""

    @pytest.mark.asyncio
    async def test_reflect_on_success(self):
        """测试成功结果的反思"""
        reflector = Reflector()

        result = {
            "text": "这是一篇高质量的文案，包含了所有关键要素，长度适中，语言流畅。" * 10
        }

        reflection = await reflector.reflect(
            goal="生成高质量文案",
            result=result,
            success_criteria="文案长度 > 100 字，包含关键词"
        )

        assert isinstance(reflection, Reflection)
        assert reflection.success is not None
        assert 0 <= reflection.score <= 10
        assert isinstance(reflection.needs_retry, bool)

    @pytest.mark.asyncio
    async def test_reflect_on_failure(self):
        """测试失败结果的反思"""
        reflector = Reflector()

        result = {
            "text": "太短了"
        }

        reflection = await reflector.reflect(
            goal="生成高质量文案",
            result=result,
            success_criteria="文案长度 > 100 字"
        )

        assert reflection.score < 7.0, "Low quality result should have low score"
        assert reflection.needs_retry, "Low score should trigger retry"
        assert len(reflection.improvement_suggestions) > 0, "Should provide improvement suggestions"

    @pytest.mark.asyncio
    async def test_reflection_has_reasoning(self):
        """测试反思包含推理过程"""
        reflector = Reflector()

        result = {"text": "测试内容" * 50}

        reflection = await reflector.reflect(
            goal="生成内容",
            result=result,
            success_criteria="内容质量高"
        )

        assert len(reflection.strengths) > 0 or len(reflection.weaknesses) > 0, \
            "Reflection should identify strengths or weaknesses"

    @pytest.mark.asyncio
    async def test_compare_multiple_results(self):
        """测试比较多个结果"""
        reflector = Reflector()

        results = [
            {"text": "短文案"},
            {"text": "这是一篇中等长度的文案，包含了一些关键信息。" * 5},
            {"text": "这是一篇非常详细和高质量的文案，包含了所有必要的元素，语言优美，结构清晰。" * 10}
        ]

        best_idx = await reflector.compare_results(
            goal="生成高质量文案",
            results=results,
            success_criteria="文案长度适中，质量高"
        )

        assert 0 <= best_idx < len(results)
        # 通常最长的文案应该得分最高（在这个测试中）
        assert best_idx == 2, "Longest and most detailed content should be best"

    @pytest.mark.asyncio
    async def test_reflection_confidence(self):
        """测试反思的置信度"""
        reflector = Reflector()

        result = {"text": "测试" * 100}

        reflection = await reflector.reflect(
            goal="生成内容",
            result=result,
            success_criteria="内容质量高"
        )

        assert 0 <= reflection.confidence <= 1.0, "Confidence should be between 0 and 1"


class TestPlanningIntegration:
    """测试 Planning 和 Reflection 的集成"""

    @pytest.mark.asyncio
    async def test_plan_execute_reflect_cycle(self):
        """测试完整的计划-执行-反思循环"""
        planner = Planner()
        reflector = Reflector()

        # 1. 创建计划
        plan = await planner.create_plan(
            task="生成小红书内容",
            context={"platform": "xiaohongshu"},
            max_steps=3
        )

        assert len(plan.steps) > 0

        # 2. 模拟执行每个步骤并反思
        for step in plan.steps:
            # 模拟执行结果
            mock_result = {
                "step_id": step.step_id,
                "output": f"完成了{step.goal}"
            }

            # 反思
            reflection = await reflector.reflect(
                goal=step.goal,
                result=mock_result,
                success_criteria=step.success_criteria
            )

            assert isinstance(reflection, Reflection)

            # 如果需要重试，可以重新规划
            if reflection.needs_retry:
                new_plan = await planner.replan(
                    original_plan=plan,
                    failed_step=step,
                    failure_reason="; ".join(reflection.improvement_suggestions)
                )
                assert isinstance(new_plan, Plan)

    @pytest.mark.asyncio
    async def test_adaptive_planning(self):
        """测试自适应规划"""
        planner = Planner()

        # 简单任务应该生成较少步骤
        simple_plan = await planner.create_plan(
            task="生成简短文案",
            context={"platform": "xiaohongshu"},
            max_steps=5
        )

        # 复杂任务应该生成更多步骤
        complex_plan = await planner.create_plan(
            task="生成包含多个部分的复杂内容，需要研究、规划、撰写、审核、优化",
            context={"platform": "xiaohongshu"},
            max_steps=5
        )

        # 复杂任务的步骤数应该 >= 简单任务
        assert len(complex_plan.steps) >= len(simple_plan.steps) or \
               complex_plan.complexity in ["medium", "complex"]


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
