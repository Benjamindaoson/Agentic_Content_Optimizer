"""
Agent Benchmark - Agent 性能基准测试

系统化评估 Agent 的性能：
1. 内容生成成功率
2. 内容质量评分
3. 任务完成时间
4. 错误率和重试率
5. 多维度对比
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import asyncio
import logging
import json
import numpy as np

from app.agents.content.writer_agent_v2 import WriterAgentV2
from app.agents.content.critic_agent_v2 import CriticAgentV2
from app.agents.workflow.langgraph_workflow import ContentGenerationWorkflow

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkTask:
    """基准测试任务"""
    task_id: str
    topic: str
    platform: str
    difficulty: str  # easy/medium/hard
    expected_quality: float  # 期望质量分数
    timeout_seconds: int = 60


@dataclass
class BenchmarkResult:
    """基准测试结果"""
    task_id: str
    success: bool
    quality_score: float
    execution_time_seconds: float
    num_retries: int
    error_message: Optional[str]
    generated_content: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkReport:
    """基准测试报告"""
    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    success_rate: float
    avg_quality_score: float
    avg_execution_time: float
    avg_retries: float
    quality_distribution: Dict[str, int]
    difficulty_breakdown: Dict[str, Dict[str, Any]]
    detailed_results: List[BenchmarkResult]


class AgentBenchmark:
    """
    Agent 基准测试系统

    核心功能：
    1. 创建测试任务集
    2. 执行基准测试
    3. 评估 Agent 性能
    4. 生成对比报告
    """

    def __init__(self):
        """初始化 Agent Benchmark"""
        self.workflow = ContentGenerationWorkflow()

        logger.info("AgentBenchmark initialized")

    def create_default_tasks(self) -> List[BenchmarkTask]:
        """创建默认测试任务集

        Returns:
            测试任务列表
        """
        tasks = [
            # 简单任务
            BenchmarkTask(
                task_id="easy_001",
                topic="AI 写作工具推荐",
                platform="xiaohongshu",
                difficulty="easy",
                expected_quality=7.0,
                timeout_seconds=30
            ),
            BenchmarkTask(
                task_id="easy_002",
                topic="如何提高工作效率",
                platform="weibo",
                difficulty="easy",
                expected_quality=7.0,
                timeout_seconds=30
            ),
            BenchmarkTask(
                task_id="easy_003",
                topic="短视频拍摄技巧",
                platform="douyin",
                difficulty="easy",
                expected_quality=7.0,
                timeout_seconds=30
            ),

            # 中等任务
            BenchmarkTask(
                task_id="medium_001",
                topic="如何用 AI 工具打造个人品牌",
                platform="xiaohongshu",
                difficulty="medium",
                expected_quality=8.0,
                timeout_seconds=45
            ),
            BenchmarkTask(
                task_id="medium_002",
                topic="从 0 到 1 的副业赚钱指南",
                platform="weibo",
                difficulty="medium",
                expected_quality=8.0,
                timeout_seconds=45
            ),
            BenchmarkTask(
                task_id="medium_003",
                topic="如何提高短视频完播率和互动率",
                platform="douyin",
                difficulty="medium",
                expected_quality=8.0,
                timeout_seconds=45
            ),

            # 困难任务
            BenchmarkTask(
                task_id="hard_001",
                topic="AI 时代的内容创作者如何实现商业变现的完整策略",
                platform="xiaohongshu",
                difficulty="hard",
                expected_quality=8.5,
                timeout_seconds=60
            ),
            BenchmarkTask(
                task_id="hard_002",
                topic="构建个人 IP 矩阵的系统化方法论",
                platform="weibo",
                difficulty="hard",
                expected_quality=8.5,
                timeout_seconds=60
            ),
            BenchmarkTask(
                task_id="hard_003",
                topic="从 0 到 100 万粉丝的抖音账号运营全流程",
                platform="douyin",
                difficulty="hard",
                expected_quality=8.5,
                timeout_seconds=60
            ),
        ]

        logger.info(f"Created {len(tasks)} default benchmark tasks")
        return tasks

    async def run_single_task(
        self,
        task: BenchmarkTask
    ) -> BenchmarkResult:
        """执行单个测试任务

        Args:
            task: 测试任务

        Returns:
            测试结果
        """
        logger.info(f"Running task: {task.task_id} - {task.topic}")

        start_time = datetime.now()
        num_retries = 0
        error_message = None
        generated_content = None
        quality_score = 0.0

        try:
            # 执行工作流
            result = await asyncio.wait_for(
                self.workflow.generate_content(
                    topic=task.topic,
                    platform=task.platform,
                    max_iterations=3
                ),
                timeout=task.timeout_seconds
            )

            # 提取结果
            if result.get("status") == "completed":
                generated_content = result.get("final_content")
                quality_score = result.get("final_score", 0.0)
                num_retries = result.get("iterations", 1) - 1
                success = True
            else:
                success = False
                error_message = result.get("error", "Unknown error")

        except asyncio.TimeoutError:
            success = False
            error_message = f"Timeout after {task.timeout_seconds}s"
            logger.warning(f"Task {task.task_id} timed out")

        except Exception as e:
            success = False
            error_message = str(e)
            logger.error(f"Task {task.task_id} failed: {e}", exc_info=True)

        # 计算执行时间
        execution_time = (datetime.now() - start_time).total_seconds()

        result = BenchmarkResult(
            task_id=task.task_id,
            success=success,
            quality_score=quality_score,
            execution_time_seconds=execution_time,
            num_retries=num_retries,
            error_message=error_message,
            generated_content=generated_content,
            metadata={
                "topic": task.topic,
                "platform": task.platform,
                "difficulty": task.difficulty,
                "expected_quality": task.expected_quality
            }
        )

        logger.info(
            f"Task {task.task_id} completed: "
            f"success={success}, quality={quality_score:.2f}, "
            f"time={execution_time:.2f}s"
        )

        return result

    async def run_benchmark(
        self,
        tasks: Optional[List[BenchmarkTask]] = None,
        max_concurrent: int = 3
    ) -> BenchmarkReport:
        """运行基准测试

        Args:
            tasks: 测试任务列表（None 使用默认任务）
            max_concurrent: 最大并发数

        Returns:
            基准测试报告
        """
        if tasks is None:
            tasks = self.create_default_tasks()

        logger.info(f"Running benchmark with {len(tasks)} tasks...")

        # 并发执行任务
        semaphore = asyncio.Semaphore(max_concurrent)

        async def run_with_semaphore(task):
            async with semaphore:
                return await self.run_single_task(task)

        results = await asyncio.gather(
            *[run_with_semaphore(task) for task in tasks],
            return_exceptions=True
        )

        # 过滤异常
        valid_results = [
            r for r in results
            if isinstance(r, BenchmarkResult)
        ]

        # 生成报告
        report = self._generate_report(valid_results, tasks)

        logger.info(
            f"Benchmark complete: "
            f"success_rate={report.success_rate:.1%}, "
            f"avg_quality={report.avg_quality_score:.2f}"
        )

        return report

    def _generate_report(
        self,
        results: List[BenchmarkResult],
        tasks: List[BenchmarkTask]
    ) -> BenchmarkReport:
        """生成基准测试报告

        Args:
            results: 测试结果列表
            tasks: 测试任务列表

        Returns:
            基准测试报告
        """
        total_tasks = len(results)
        successful_tasks = sum(1 for r in results if r.success)
        failed_tasks = total_tasks - successful_tasks

        success_rate = successful_tasks / total_tasks if total_tasks > 0 else 0.0

        # 计算平均指标（仅成功的任务）
        successful_results = [r for r in results if r.success]

        if successful_results:
            avg_quality_score = np.mean([r.quality_score for r in successful_results])
            avg_execution_time = np.mean([r.execution_time_seconds for r in successful_results])
            avg_retries = np.mean([r.num_retries for r in successful_results])
        else:
            avg_quality_score = 0.0
            avg_execution_time = 0.0
            avg_retries = 0.0

        # 质量分布
        quality_distribution = {
            "excellent (>=8.5)": sum(1 for r in successful_results if r.quality_score >= 8.5),
            "good (7.0-8.5)": sum(1 for r in successful_results if 7.0 <= r.quality_score < 8.5),
            "average (5.0-7.0)": sum(1 for r in successful_results if 5.0 <= r.quality_score < 7.0),
            "poor (<5.0)": sum(1 for r in successful_results if r.quality_score < 5.0)
        }

        # 按难度分组
        difficulty_breakdown = {}
        for difficulty in ["easy", "medium", "hard"]:
            difficulty_results = [
                r for r in results
                if r.metadata.get("difficulty") == difficulty
            ]

            if difficulty_results:
                difficulty_successful = [r for r in difficulty_results if r.success]

                difficulty_breakdown[difficulty] = {
                    "total": len(difficulty_results),
                    "successful": len(difficulty_successful),
                    "success_rate": len(difficulty_successful) / len(difficulty_results),
                    "avg_quality": np.mean([r.quality_score for r in difficulty_successful]) if difficulty_successful else 0.0,
                    "avg_time": np.mean([r.execution_time_seconds for r in difficulty_successful]) if difficulty_successful else 0.0
                }

        report = BenchmarkReport(
            total_tasks=total_tasks,
            successful_tasks=successful_tasks,
            failed_tasks=failed_tasks,
            success_rate=success_rate,
            avg_quality_score=avg_quality_score,
            avg_execution_time=avg_execution_time,
            avg_retries=avg_retries,
            quality_distribution=quality_distribution,
            difficulty_breakdown=difficulty_breakdown,
            detailed_results=results
        )

        return report

    def save_report(
        self,
        report: BenchmarkReport,
        output_file: str
    ):
        """保存报告到文件

        Args:
            report: 基准测试报告
            output_file: 输出文件路径
        """
        data = {
            "summary": {
                "total_tasks": report.total_tasks,
                "successful_tasks": report.successful_tasks,
                "failed_tasks": report.failed_tasks,
                "success_rate": round(report.success_rate, 4),
                "avg_quality_score": round(report.avg_quality_score, 4),
                "avg_execution_time": round(report.avg_execution_time, 2),
                "avg_retries": round(report.avg_retries, 2)
            },
            "quality_distribution": report.quality_distribution,
            "difficulty_breakdown": {
                k: {
                    "total": v["total"],
                    "successful": v["successful"],
                    "success_rate": round(v["success_rate"], 4),
                    "avg_quality": round(v["avg_quality"], 4),
                    "avg_time": round(v["avg_time"], 2)
                }
                for k, v in report.difficulty_breakdown.items()
            },
            "detailed_results": [
                {
                    "task_id": r.task_id,
                    "success": r.success,
                    "quality_score": round(r.quality_score, 2),
                    "execution_time_seconds": round(r.execution_time_seconds, 2),
                    "num_retries": r.num_retries,
                    "error_message": r.error_message,
                    "metadata": r.metadata
                }
                for r in report.detailed_results
            ]
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Report saved to {output_file}")


# 全局实例（单例）
_agent_benchmark_instance: Optional[AgentBenchmark] = None


def get_agent_benchmark() -> AgentBenchmark:
    """获取 Agent Benchmark 实例（单例）

    Returns:
        AgentBenchmark 实例
    """
    global _agent_benchmark_instance

    if _agent_benchmark_instance is None:
        _agent_benchmark_instance = AgentBenchmark()
        logger.info("Global AgentBenchmark instance created")

    return _agent_benchmark_instance
