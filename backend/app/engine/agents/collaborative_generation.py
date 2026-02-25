"""
协同内容生成系统

核心功能：
1. Writer-Critic 实时协作
2. Trend 驱动的动态调整
3. 多 Agent 协同优化
4. 实时反馈循环
"""

from typing import Dict, Any, Optional
import logging

from app.messaging.message_bus import MessageBus, MessageType
from app.engine.agents.base import AgentResponse

logger = logging.getLogger(__name__)


class CollaborativeContentGenerator:
    """协同内容生成器

    协调多个 Agent 协同生成内容，实现：
    - 实时反馈循环
    - 动态质量优化
    - 多轮迭代改进
    """

    def __init__(self, message_bus: MessageBus):
        """初始化协同生成器

        Args:
            message_bus: 消息总线
        """
        self.message_bus = message_bus

    async def generate_with_realtime_feedback(
        self,
        topic: str,
        platform: str,
        max_iterations: int = 3,
        quality_threshold: float = 8.0
    ) -> Dict[str, Any]:
        """实时反馈的内容生成

        流程：
        1. Trend Agent 提供趋势数据
        2. Writer Agent 生成内容
        3. Critic Agent 实时评估
        4. Writer Agent 根据反馈调整
        5. 迭代优化直到达标

        Args:
            topic: 主题
            platform: 平台
            max_iterations: 最大迭代次数
            quality_threshold: 质量阈值

        Returns:
            生成结果
        """
        logger.info(f"Starting collaborative generation for topic: {topic}, platform: {platform}")

        # 1. 获取趋势数据
        trend_response = await self.message_bus.request_response(
            "TrendAgent",
            {
                "topic": topic,
                "platform": platform,
                "limit": 5
            },
            timeout=30
        )

        if not trend_response:
            return {
                "status": "failed",
                "error": "Failed to get trend data",
                "iterations": 0
            }

        references = trend_response["response"]["data"].get("references", [])
        geo_keywords = trend_response["response"]["data"].get("geo_constraints", {}).get("keywords", [])

        logger.info(f"Retrieved {len(references)} references and {len(geo_keywords)} GEO keywords")

        # 2. 迭代生成和优化
        best_content = None
        best_score = 0.0
        feedback_history = []

        for iteration in range(max_iterations):
            logger.info(f"Iteration {iteration + 1}/{max_iterations}")

            # 生成内容
            writer_request = {
                "topic": topic,
                "platform": platform,
                "references": references,
                "geo_keywords": geo_keywords,
                "iteration": iteration,
                "previous_feedback": feedback_history[-1] if feedback_history else None
            }

            writer_response = await self.message_bus.request_response(
                "WriterAgent",
                writer_request,
                timeout=60
            )

            if not writer_response or not writer_response["response"]["success"]:
                logger.error(f"Writer Agent failed at iteration {iteration + 1}")
                continue

            generated_contents = writer_response["response"]["data"].get("generated_contents", [])
            if not generated_contents:
                logger.error(f"No content generated at iteration {iteration + 1}")
                continue

            generated_content = generated_contents[0]

            # 实时评估
            critic_request = {
                "topic": topic,
                "platform": platform,
                "generated_contents": [generated_content],
                "references": references
            }

            critic_response = await self.message_bus.request_response(
                "CriticAgent",
                critic_request,
                timeout=30
            )

            if not critic_response or not critic_response["response"]["success"]:
                logger.error(f"Critic Agent failed at iteration {iteration + 1}")
                continue

            evaluations = critic_response["response"]["data"].get("evaluations", [])
            if not evaluations:
                logger.error(f"No evaluation at iteration {iteration + 1}")
                continue

            evaluation = evaluations[0]
            current_score = evaluation["scores"].get("overall_score", 0.0)

            logger.info(f"Iteration {iteration + 1} score: {current_score}")

            # 更新最佳内容
            if current_score > best_score:
                best_content = generated_content
                best_score = current_score

            # 检查是否达标
            if evaluation["decision"] == "APPROVED" and current_score >= quality_threshold:
                logger.info(f"Content approved at iteration {iteration + 1} with score {current_score}")
                return {
                    "status": "success",
                    "content": generated_content,
                    "evaluation": evaluation,
                    "score": current_score,
                    "iterations": iteration + 1,
                    "feedback_history": feedback_history
                }

            # 发送反馈给 Writer Agent
            feedback = {
                "evaluation": evaluation,
                "suggestions": evaluation.get("improvement_suggestions", []),
                "current_score": current_score,
                "target_score": quality_threshold
            }

            feedback_history.append(feedback)

            await self.message_bus.publish(
                "feedback.WriterAgent",
                {
                    "from": "CriticAgent",
                    "feedback": feedback
                },
                MessageType.AGENT_FEEDBACK,
                sender="CollaborativeGenerator"
            )

        # 达到最大迭代次数，返回最佳结果
        logger.info(f"Max iterations reached. Best score: {best_score}")
        return {
            "status": "max_iterations_reached",
            "content": best_content,
            "score": best_score,
            "iterations": max_iterations,
            "feedback_history": feedback_history
        }

    async def generate_with_director(
        self,
        topic: str,
        platform: str,
        num_strategies: int = 3,
        max_iterations: int = 2
    ) -> Dict[str, Any]:
        """使用 Director Agent 的协同生成

        流程：
        1. Trend Agent 提供参考内容
        2. Director Agent 采样多个策略
        3. Writer Agent 为每个策略生成内容
        4. Critic Agent 评估所有内容
        5. 选择最佳内容

        Args:
            topic: 主题
            platform: 平台
            num_strategies: 策略数量
            max_iterations: 最大迭代次数

        Returns:
            生成结果
        """
        logger.info(f"Starting director-guided generation for topic: {topic}")

        # 1. 获取趋势数据
        trend_response = await self.message_bus.request_response(
            "TrendAgent",
            {"topic": topic, "platform": platform, "limit": 5},
            timeout=30
        )

        if not trend_response:
            return {"status": "failed", "error": "Failed to get trend data"}

        references = trend_response["response"]["data"].get("references", [])

        # 2. 获取多个策略
        director_response = await self.message_bus.request_response(
            "DirectorAgent",
            {
                "topic": topic,
                "references": references,
                "num_strategies": num_strategies
            },
            timeout=30
        )

        if not director_response:
            return {"status": "failed", "error": "Failed to get strategies"}

        strategies = director_response["response"]["data"].get("strategies", [])

        # 3. 为每个策略生成内容
        all_contents = []
        for idx, strategy in enumerate(strategies):
            logger.info(f"Generating content for strategy {idx + 1}/{len(strategies)}")

            writer_response = await self.message_bus.request_response(
                "WriterAgent",
                {
                    "topic": topic,
                    "platform": platform,
                    "references": references,
                    "strategy": strategy
                },
                timeout=60
            )

            if writer_response and writer_response["response"]["success"]:
                contents = writer_response["response"]["data"].get("generated_contents", [])
                all_contents.extend(contents)

        if not all_contents:
            return {"status": "failed", "error": "No content generated"}

        # 4. 评估所有内容
        critic_response = await self.message_bus.request_response(
            "CriticAgent",
            {
                "topic": topic,
                "platform": platform,
                "generated_contents": all_contents,
                "references": references
            },
            timeout=30
        )

        if not critic_response:
            return {"status": "failed", "error": "Failed to evaluate content"}

        evaluations = critic_response["response"]["data"].get("evaluations", [])

        # 5. 选择最佳内容
        best_idx = 0
        best_score = 0.0
        for idx, evaluation in enumerate(evaluations):
            score = evaluation["scores"].get("overall_score", 0.0)
            if score > best_score:
                best_score = score
                best_idx = idx

        return {
            "status": "success",
            "content": all_contents[best_idx],
            "evaluation": evaluations[best_idx],
            "score": best_score,
            "total_candidates": len(all_contents),
            "strategies_used": len(strategies)
        }
