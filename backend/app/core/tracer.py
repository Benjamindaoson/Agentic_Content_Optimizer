"""
生成追踪系统 - 完整记录每次生成的全过程
用于调试、优化、回归测试
"""

from typing import Dict, Any, Optional, List
import logging
import hashlib
import json
from datetime import datetime
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert

logger = logging.getLogger(__name__)


class GenerationTrace:
    """生成追踪记录"""

    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self.timestamp = datetime.now().isoformat()
        self.start_time = datetime.now()
        self.end_time = None
        self.stages = {}
        self.metadata = {}

    def add_stage(self, stage_name: str, data: Dict[str, Any]):
        """添加阶段数据"""
        self.stages[stage_name] = {
            'timestamp': datetime.now().isoformat(),
            'data': data
        }

    def add_metadata(self, key: str, value: Any):
        """添加元数据"""
        self.metadata[key] = value

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'trace_id': self.trace_id,
            'timestamp': self.timestamp,
            'stages': self.stages,
            'metadata': self.metadata
        }


class GenerationTracer:
    """
    生成追踪器

    功能：
    1. 记录完整的生成流程
    2. 追踪每个阶段的输入输出
    3. 记录模型版本、参数、prompt hash
    4. 支持查询和分析
    """

    def __init__(self, db_session: Optional[AsyncSession] = None):
        self.db = db_session
        self.current_trace: Optional[GenerationTrace] = None

    def start_trace(self, user_id: str, input_data: Dict[str, Any]) -> str:
        """开始一次追踪"""
        trace_id = str(uuid4())
        self.current_trace = GenerationTrace(trace_id)

        # 记录基本信息
        self.current_trace.add_metadata('user_id', user_id)
        self.current_trace.add_metadata('input', input_data)

        logger.info(f"Started trace: {trace_id}")
        return trace_id

    def trace_trend_retrieval(
        self,
        geo_keywords: List[str],
        references: List[Dict[str, Any]],
        quality_scores: Optional[List[float]] = None
    ):
        """追踪趋势检索阶段"""
        if not self.current_trace:
            logger.warning("No active trace")
            return

        self.current_trace.add_stage('trend_retrieval', {
            'geo_keywords': geo_keywords,
            'references_count': len(references),
            'references': references,
            'quality_scores': quality_scores or []
        })

    def trace_strategy_selection(
        self,
        actions: List[Dict[str, str]],
        diversity_score: float,
        exploration: bool,
        policy_version: Optional[str] = None
    ):
        """追踪策略选择阶段"""
        if not self.current_trace:
            logger.warning("No active trace")
            return

        self.current_trace.add_stage('strategy_selection', {
            'actions': actions,
            'diversity_score': diversity_score,
            'exploration': exploration,
            'policy_version': policy_version
        })

    def trace_content_generation(
        self,
        action: Dict[str, str],
        model: str,
        model_version: str,
        prompt: str,
        temperature: float,
        generated_content: Dict[str, Any]
    ):
        """追踪内容生成阶段"""
        if not self.current_trace:
            logger.warning("No active trace")
            return

        # 计算 prompt hash（用于去重和版本控制）
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()

        self.current_trace.add_stage('content_generation', {
            'action': action,
            'model': model,
            'model_version': model_version,
            'prompt_hash': prompt_hash,
            'prompt_length': len(prompt),
            'temperature': temperature,
            'generated_content': generated_content
        })

    def trace_quality_evaluation(
        self,
        critic_scores: Dict[str, Any],
        reward_components: Dict[str, Any],
        total_reward: float,
        approved: bool
    ):
        """追踪质量评估阶段"""
        if not self.current_trace:
            logger.warning("No active trace")
            return

        self.current_trace.add_stage('quality_evaluation', {
            'critic_scores': critic_scores,
            'reward_components': reward_components,
            'total_reward': total_reward,
            'approved': approved
        })

    def trace_policy_update(
        self,
        policy_before: Dict[str, float],
        policy_after: Dict[str, float],
        update_magnitude: float
    ):
        """追踪策略更新阶段"""
        if not self.current_trace:
            logger.warning("No active trace")
            return

        self.current_trace.add_stage('policy_update', {
            'policy_before': policy_before,
            'policy_after': policy_after,
            'update_magnitude': update_magnitude
        })

    async def end_trace(self, output_data: Dict[str, Any]) -> str:
        """结束追踪并保存"""
        if not self.current_trace:
            logger.warning("No active trace")
            return ""

        # 设置结束时间
        self.current_trace.end_time = datetime.now()

        # 添加输出数据
        self.current_trace.add_metadata('output', output_data)
        self.current_trace.add_metadata('end_time', self.current_trace.end_time.isoformat())

        # 计算总耗时
        duration = (self.current_trace.end_time - self.current_trace.start_time).total_seconds()
        self.current_trace.add_metadata('duration_seconds', duration)

        # 保存到数据库
        if self.db:
            await self._save_to_db(self.current_trace)

        trace_id = self.current_trace.trace_id
        logger.info(f"Ended trace: {trace_id}, duration: {duration:.2f}s")

        # 清空当前追踪
        self.current_trace = None

        return trace_id

    async def _save_to_db(self, trace: GenerationTrace):
        """保存到数据库"""
        try:
            from app.models.generation_trace import GenerationTraceModel

            # 转换为字典
            trace_data = trace.to_dict()

            # 计算持续时间（毫秒）
            duration_ms = None
            if trace.end_time and trace.start_time:
                duration_ms = int((trace.end_time - trace.start_time).total_seconds() * 1000)

            # 创建数据库记录
            db_trace = GenerationTraceModel(
                trace_id=trace.trace_id,
                user_id=trace.metadata.get('user_id'),
                data=trace_data,  # SQLAlchemy 会自动处理 JSON
                status="completed" if trace.end_time else "in_progress",
                duration=duration_ms
            )

            # 保存到数据库
            self.db.add(db_trace)
            await self.db.commit()
            await self.db.refresh(db_trace)

            logger.info(f"Trace saved to DB: {trace.trace_id}, duration: {duration_ms}ms")

        except Exception as e:
            logger.error(f"Failed to save trace to DB: {e}")
            await self.db.rollback()

    async def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """获取追踪记录"""
        if not self.db:
            return None

        try:
            from app.models.generation_trace import GenerationTraceModel

            # 从数据库查询
            result = await self.db.execute(
                select(GenerationTraceModel).where(GenerationTraceModel.trace_id == trace_id)
            )
            trace_model = result.scalar_one_or_none()

            if trace_model:
                return trace_model.data

            return None

        except Exception as e:
            logger.error(f"Failed to get trace: {e}")
            return None

    async def query_traces(
        self,
        user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """查询追踪记录"""
        if not self.db:
            return []

        try:
            from app.models.generation_trace import GenerationTraceModel

            # 构建查询
            query = select(GenerationTraceModel)

            if user_id:
                query = query.where(GenerationTraceModel.user_id == user_id)

            if start_time:
                query = query.where(GenerationTraceModel.created_at >= start_time)

            if end_time:
                query = query.where(GenerationTraceModel.created_at <= end_time)

            if status:
                query = query.where(GenerationTraceModel.status == status)

            # 按创建时间倒序
            query = query.order_by(GenerationTraceModel.created_at.desc())
            query = query.limit(limit)

            # 执行查询
            result = await self.db.execute(query)
            trace_models = result.scalars().all()

            return [trace.data for trace in trace_models]

        except Exception as e:
            logger.error(f"Failed to query traces: {e}")
            return []


class TraceAnalyzer:
    """追踪分析器 - 用于分析生成质量和性能"""

    def __init__(self, tracer: GenerationTracer):
        self.tracer = tracer

    async def analyze_performance(
        self,
        user_id: Optional[str] = None,
        time_range: Optional[tuple] = None
    ) -> Dict[str, Any]:
        """分析性能指标"""

        traces = await self.tracer.query_traces(
            user_id=user_id,
            start_time=time_range[0] if time_range else None,
            end_time=time_range[1] if time_range else None
        )

        if not traces:
            return {}

        # 统计指标
        durations = [t['metadata'].get('duration_seconds', 0) for t in traces]
        rewards = []
        approval_rates = []

        for trace in traces:
            eval_stage = trace['stages'].get('quality_evaluation', {})
            if eval_stage:
                rewards.append(eval_stage['data'].get('total_reward', 0))
                approval_rates.append(1 if eval_stage['data'].get('approved') else 0)

        return {
            'total_generations': len(traces),
            'avg_duration': sum(durations) / len(durations) if durations else 0,
            'avg_reward': sum(rewards) / len(rewards) if rewards else 0,
            'approval_rate': sum(approval_rates) / len(approval_rates) if approval_rates else 0,
            'p50_duration': sorted(durations)[len(durations) // 2] if durations else 0,
            'p95_duration': sorted(durations)[int(len(durations) * 0.95)] if durations else 0
        }

    async def analyze_model_performance(
        self,
        model_name: str,
        time_range: Optional[tuple] = None
    ) -> Dict[str, Any]:
        """分析特定模型的性能"""

        traces = await self.tracer.query_traces(
            start_time=time_range[0] if time_range else None,
            end_time=time_range[1] if time_range else None
        )

        # 过滤特定模型
        model_traces = [
            t for t in traces
            if t['stages'].get('content_generation', {}).get('data', {}).get('model') == model_name
        ]

        if not model_traces:
            return {}

        # 统计
        rewards = []
        latencies = []

        for trace in model_traces:
            eval_stage = trace['stages'].get('quality_evaluation', {})
            if eval_stage:
                rewards.append(eval_stage['data'].get('total_reward', 0))

            # 计算生成阶段耗时
            gen_stage = trace['stages'].get('content_generation', {})
            if gen_stage:
                # 简化版：使用总耗时
                latencies.append(trace['metadata'].get('duration_seconds', 0))

        return {
            'model': model_name,
            'total_generations': len(model_traces),
            'avg_reward': sum(rewards) / len(rewards) if rewards else 0,
            'avg_latency': sum(latencies) / len(latencies) if latencies else 0,
            'success_rate': len([r for r in rewards if r > 0.5]) / len(rewards) if rewards else 0
        }

    async def compare_strategies(
        self,
        strategy_a: str,
        strategy_b: str,
        time_range: Optional[tuple] = None
    ) -> Dict[str, Any]:
        """对比两个策略的效果"""

        traces = await self.tracer.query_traces(
            start_time=time_range[0] if time_range else None,
            end_time=time_range[1] if time_range else None
        )

        # 分组
        traces_a = []
        traces_b = []

        for trace in traces:
            strategy_stage = trace['stages'].get('strategy_selection', {})
            if strategy_stage:
                # 简化版：根据 policy_version 区分
                policy_version = strategy_stage['data'].get('policy_version', '')
                if strategy_a in policy_version:
                    traces_a.append(trace)
                elif strategy_b in policy_version:
                    traces_b.append(trace)

        # 统计对比
        def get_stats(traces_list):
            if not traces_list:
                return {}

            rewards = []
            for t in traces_list:
                eval_stage = t['stages'].get('quality_evaluation', {})
                if eval_stage:
                    rewards.append(eval_stage['data'].get('total_reward', 0))

            return {
                'count': len(traces_list),
                'avg_reward': sum(rewards) / len(rewards) if rewards else 0,
                'max_reward': max(rewards) if rewards else 0,
                'min_reward': min(rewards) if rewards else 0
            }

        return {
            'strategy_a': {
                'name': strategy_a,
                'stats': get_stats(traces_a)
            },
            'strategy_b': {
                'name': strategy_b,
                'stats': get_stats(traces_b)
            },
            'winner': strategy_a if get_stats(traces_a).get('avg_reward', 0) > get_stats(traces_b).get('avg_reward', 0) else strategy_b
        }
