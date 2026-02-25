"""
Reflector - Agent 反思模块

实现执行结果的自我评估和改进建议
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from app.engine.llm.unified import UnifiedLLM
import logging

logger = logging.getLogger(__name__)


class Reflection(BaseModel):
    """反思结果"""
    success: bool = Field(..., description="是否成功")
    score: float = Field(..., ge=0, le=10, description="质量评分 (0-10)")
    strengths: list[str] = Field(default_factory=list, description="优点")
    weaknesses: list[str] = Field(default_factory=list, description="缺点")
    needs_retry: bool = Field(default=False, description="是否需要重试")
    improvement_suggestions: list[str] = Field(default_factory=list, description="改进建议")
    confidence: float = Field(default=0.8, ge=0, le=1, description="判断置信度")


class Reflector:
    """反思器

    评估 Agent 执行结果，提供改进建议
    """

    def __init__(self, llm: Optional[UnifiedLLM] = None):
        self.llm = llm or UnifiedLLM()
        self.retry_threshold = 7.0  # 低于此分数需要重试

    async def reflect(
        self,
        goal: str,
        result: Any,
        success_criteria: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Reflection:
        """反思执行结果

        Args:
            goal: 步骤目标
            result: 执行结果
            success_criteria: 成功标准
            context: 额外上下文

        Returns:
            Reflection: 反思结果
        """
        logger.info(f"Reflecting on goal: {goal}")

        # 构建 Reflection Prompt
        prompt = self._build_reflection_prompt(goal, result, success_criteria, context)

        # 调用 LLM 进行反思
        response = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            provider="claude",
            model="sonnet-4.5",
            temperature=0.2,  # 低温度确保评估客观
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "reflection_result",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean"},
                            "score": {"type": "number", "minimum": 0, "maximum": 10},
                            "strengths": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "weaknesses": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "needs_retry": {"type": "boolean"},
                            "improvement_suggestions": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                        },
                        "required": ["success", "score", "needs_retry"]
                    }
                }
            }
        )

        # 解析响应
        reflection = Reflection(**response)

        # 自动判断是否需要重试
        if reflection.score < self.retry_threshold and not reflection.needs_retry:
            reflection.needs_retry = True
            logger.info(f"Auto-set needs_retry=True due to low score: {reflection.score}")

        logger.info(f"Reflection complete: score={reflection.score}, needs_retry={reflection.needs_retry}")
        return reflection

    def _build_reflection_prompt(
        self,
        goal: str,
        result: Any,
        success_criteria: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """构建 Reflection Prompt"""

        result_str = self._format_result(result)
        context_str = self._format_context(context) if context else "无"

        prompt = f"""你是一个严格的质量评估专家。请评估以下执行结果是否达成目标。

**目标**: {goal}

**成功标准**: {success_criteria}

**执行结果**:
{result_str}

**上下文**:
{context_str}

**评估要求**:
1. 客观评估是否达成目标
2. 给出 0-10 分的质量评分（8分以上为优秀，7分为及格，低于7分需要重试）
3. 列出优点和缺点
4. 如果未达标，提供具体的改进建议

**输出格式**:
{{
    "success": true/false,
    "score": 0-10,
    "strengths": ["优点1", "优点2"],
    "weaknesses": ["缺点1", "缺点2"],
    "needs_retry": true/false,
    "improvement_suggestions": ["建议1", "建议2"],
    "confidence": 0.0-1.0
}}

请开始评估:"""

        return prompt

    def _format_result(self, result: Any) -> str:
        """格式化结果用于展示"""
        if isinstance(result, dict):
            # 提取关键字段
            if "text_structure" in result:
                text = result["text_structure"].get("full_text", "")
                return f"生成文案（{len(text)}字）:\n{text[:500]}..."
            elif "evaluation" in result:
                return f"评估结果: {result['evaluation']}"
            else:
                return str(result)[:500]
        elif isinstance(result, str):
            return result[:500]
        else:
            return str(result)[:500]

    def _format_context(self, context: Dict[str, Any]) -> str:
        """格式化上下文"""
        lines = []
        for key, value in context.items():
            if isinstance(value, (list, dict)):
                lines.append(f"- {key}: {len(value)} 项")
            else:
                lines.append(f"- {key}: {value}")
        return "\n".join(lines)

    async def compare_results(
        self,
        goal: str,
        results: list[Any],
        success_criteria: str
    ) -> int:
        """比较多个结果，返回最佳结果的索引

        Args:
            goal: 目标
            results: 多个执行结果
            success_criteria: 成功标准

        Returns:
            int: 最佳结果的索引
        """
        logger.info(f"Comparing {len(results)} results")

        reflections = []
        for i, result in enumerate(results):
            reflection = await self.reflect(goal, result, success_criteria)
            reflections.append((i, reflection))

        # 按分数排序
        reflections.sort(key=lambda x: x[1].score, reverse=True)

        best_idx = reflections[0][0]
        best_score = reflections[0][1].score

        logger.info(f"Best result: index={best_idx}, score={best_score}")
        return best_idx
