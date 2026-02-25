"""
模型路由器 - 智能路由 + 灰度发布 + 降级
Model Router with Canary Deployment and Fallback
"""

from typing import Dict, Any, Optional, List, Callable
import logging
import random
import time
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """任务类型"""
    TREND_EXTRACTION = "trend_extraction"
    CONTENT_GENERATION = "content_generation"
    QUALITY_EVALUATION = "quality_evaluation"
    STRATEGY_SELECTION = "strategy_selection"


@dataclass
class ModelConfig:
    """模型配置"""
    name: str
    provider: str  # 'claude', 'deepseek', 'gemini'
    version: str
    max_tokens: int = 4000
    temperature: float = 0.7
    timeout: float = 30.0
    cost_per_1k_tokens: float = 0.01


@dataclass
class RoutingRule:
    """路由规则"""
    task_type: TaskType
    primary_model: str
    fallback_models: List[str] = field(default_factory=list)
    weight: float = 1.0  # 用于负载均衡


@dataclass
class CanaryConfig:
    """灰度配置"""
    enabled: bool = False
    canary_model: str = ""
    traffic_percent: float = 10.0  # 灰度流量百分比
    success_threshold: float = 0.95  # 成功率阈值
    min_requests: int = 100  # 最小请求数


@dataclass
class ModelMetrics:
    """模型指标"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency: float = 0.0
    total_cost: float = 0.0
    consecutive_failures: int = 0  # 连续失败次数
    circuit_breaker_open: bool = False  # 熔断器状态
    circuit_breaker_open_time: Optional[float] = None  # 熔断器打开时间

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    @property
    def avg_latency(self) -> float:
        if self.successful_requests == 0:
            return 0.0
        return self.total_latency / self.successful_requests

    @property
    def avg_cost(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_cost / self.total_requests


class ModelRouter:
    """
    模型路由器

    功能：
    1. 智能路由（根据任务类型选择最佳模型）
    2. 灰度发布（新模型逐步放量）
    3. 自动降级（失败时切换到备用模型）
    4. 性能监控（延迟、成功率、成本）
    5. 负载均衡
    """

    def __init__(
        self,
        models: Dict[str, ModelConfig],
        routing_rules: List[RoutingRule],
        canary_config: Optional[CanaryConfig] = None,
        max_consecutive_failures: int = 5,  # 最大连续失败次数
        circuit_breaker_timeout: float = 60.0,  # 熔断器超时时间（秒）
        max_fallback_attempts: int = 3  # 最大降级尝试次数
    ):
        """
        初始化模型路由器

        Args:
            models: 模型配置字典 {model_name: ModelConfig}
            routing_rules: 路由规则列表
            canary_config: 灰度配置
            max_consecutive_failures: 最大连续失败次数，超过后触发熔断
            circuit_breaker_timeout: 熔断器超时时间（秒）
            max_fallback_attempts: 最大降级尝试次数
        """
        self.models = models
        self.routing_rules = {rule.task_type: rule for rule in routing_rules}
        self.canary_config = canary_config or CanaryConfig()

        # 降级限制参数
        self.max_consecutive_failures = max_consecutive_failures
        self.circuit_breaker_timeout = circuit_breaker_timeout
        self.max_fallback_attempts = max_fallback_attempts

        # 指标追踪
        self.metrics: Dict[str, ModelMetrics] = {
            name: ModelMetrics() for name in models.keys()
        }

        # 模型实例缓存（需要外部注入）
        self.model_instances: Dict[str, Any] = {}

        logger.info(
            f"Model Router initialized with {len(models)} models, "
            f"canary={'enabled' if self.canary_config.enabled else 'disabled'}, "
            f"max_fallback_attempts={max_fallback_attempts}"
        )

    def register_model_instance(self, model_name: str, instance: Any):
        """注册模型实例"""
        self.model_instances[model_name] = instance
        logger.info(f"Model instance registered: {model_name}")

    async def route(
        self,
        task_type: TaskType,
        prompt: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        路由请求到合适的模型

        Args:
            task_type: 任务类型
            prompt: 提示词
            **kwargs: 其他参数

        Returns:
            模型响应
        """

        # 1. 选择模型
        model_name = self._select_model(task_type)

        # 2. 执行请求（带降级）
        result = await self._execute_with_fallback(
            model_name=model_name,
            task_type=task_type,
            prompt=prompt,
            **kwargs
        )

        return result

    def _select_model(self, task_type: TaskType) -> str:
        """选择模型"""

        # 获取路由规则
        rule = self.routing_rules.get(task_type)
        if not rule:
            logger.warning(f"No routing rule for task type: {task_type}")
            return list(self.models.keys())[0]  # 默认第一个

        # 灰度逻辑
        if self.canary_config.enabled and self.canary_config.canary_model:
            if random.random() < self.canary_config.traffic_percent / 100:
                logger.debug(f"Canary traffic: using {self.canary_config.canary_model}")
                return self.canary_config.canary_model

        # 正常路由
        return rule.primary_model

    async def _execute_with_fallback(
        self,
        model_name: str,
        task_type: TaskType,
        prompt: str,
        **kwargs
    ) -> Dict[str, Any]:
        """执行请求（带降级和熔断保护）"""

        rule = self.routing_rules.get(task_type)
        fallback_models = rule.fallback_models if rule else []

        # 检查主模型熔断器状态
        if self._is_circuit_breaker_open(model_name):
            logger.warning(f"Circuit breaker open for {model_name}, skipping to fallback")
        else:
            # 尝试主模型
            result = await self._execute_single_model(
                model_name=model_name,
                prompt=prompt,
                is_primary=True,
                **kwargs
            )

            if result['success']:
                return result

        # 降级到备用模型（限制尝试次数）
        logger.warning(f"Primary model {model_name} failed, trying fallback models")

        fallback_attempts = 0
        for fallback_model in fallback_models:
            # 检查是否超过最大降级尝试次数
            if fallback_attempts >= self.max_fallback_attempts:
                logger.error(f"Reached max fallback attempts ({self.max_fallback_attempts}), stopping")
                break

            # 检查备用模型熔断器状态
            if self._is_circuit_breaker_open(fallback_model):
                logger.warning(f"Circuit breaker open for {fallback_model}, skipping")
                continue

            logger.info(f"Fallback attempt {fallback_attempts + 1}/{self.max_fallback_attempts}: {fallback_model}")

            result = await self._execute_single_model(
                model_name=fallback_model,
                prompt=prompt,
                is_primary=False,
                **kwargs
            )

            fallback_attempts += 1

            if result['success']:
                return result

        # 所有模型都失败
        logger.error(f"All models failed for task type: {task_type} after {fallback_attempts} fallback attempts")
        return {
            'success': False,
            'error': f'All models failed after {fallback_attempts} fallback attempts',
            'model': model_name,
            'fallback_attempts': fallback_attempts
        }

    async def _execute_single_model(
        self,
        model_name: str,
        prompt: str,
        is_primary: bool,
        **kwargs
    ) -> Dict[str, Any]:
        """执行单个模型"""

        model_config = self.models.get(model_name)
        if not model_config:
            logger.error(f"Model not found: {model_name}")
            return {'success': False, 'error': f'Model not found: {model_name}'}

        model_instance = self.model_instances.get(model_name)
        if not model_instance:
            logger.error(f"Model instance not registered: {model_name}")
            return {'success': False, 'error': f'Model instance not registered: {model_name}'}

        # 记录指标
        metrics = self.metrics[model_name]
        metrics.total_requests += 1

        start_time = time.time()

        try:
            # 执行模型调用
            response = await model_instance.generate(
                prompt=prompt,
                max_tokens=kwargs.get('max_tokens', model_config.max_tokens),
                temperature=kwargs.get('temperature', model_config.temperature),
                timeout=model_config.timeout
            )

            # 计算延迟
            latency = time.time() - start_time

            # 计算成本（简化版）
            token_count = len(prompt.split()) + len(str(response).split())
            cost = (token_count / 1000) * model_config.cost_per_1k_tokens

            # 更新指标
            metrics.successful_requests += 1
            metrics.total_latency += latency
            metrics.total_cost += cost
            metrics.consecutive_failures = 0  # 重置连续失败计数

            # 记录日志
            self._log_request(
                model_name=model_name,
                is_primary=is_primary,
                success=True,
                latency=latency,
                cost=cost
            )

            return {
                'success': True,
                'response': response,
                'model': model_name,
                'model_version': model_config.version,
                'latency': latency,
                'cost': cost,
                'is_canary': not is_primary and self.canary_config.enabled
            }

        except Exception as e:
            # 失败
            latency = time.time() - start_time
            metrics.failed_requests += 1
            metrics.consecutive_failures += 1

            # 检查是否需要打开熔断器
            if metrics.consecutive_failures >= self.max_consecutive_failures:
                metrics.circuit_breaker_open = True
                metrics.circuit_breaker_open_time = time.time()
                logger.error(
                    f"Circuit breaker opened for {model_name} "
                    f"after {metrics.consecutive_failures} consecutive failures"
                )

            logger.error(f"Model {model_name} failed: {e}")

            self._log_request(
                model_name=model_name,
                is_primary=is_primary,
                success=False,
                latency=latency,
                error=str(e)
            )

            return {
                'success': False,
                'error': str(e),
                'model': model_name,
                'latency': latency
            }

    def _is_circuit_breaker_open(self, model_name: str) -> bool:
        """
        检查熔断器是否打开

        如果熔断器打开且超过超时时间，则自动关闭（半开状态）

        Args:
            model_name: 模型名称

        Returns:
            熔断器是否打开
        """
        if model_name not in self.metrics:
            return False

        metrics = self.metrics[model_name]

        if not metrics.circuit_breaker_open:
            return False

        # 检查是否超过超时时间
        if metrics.circuit_breaker_open_time is None:
            return True

        elapsed = time.time() - metrics.circuit_breaker_open_time

        if elapsed >= self.circuit_breaker_timeout:
            # 超时，关闭熔断器（进入半开状态）
            metrics.circuit_breaker_open = False
            metrics.circuit_breaker_open_time = None
            metrics.consecutive_failures = 0
            logger.info(
                f"Circuit breaker closed for {model_name} "
                f"after {elapsed:.1f}s timeout (entering half-open state)"
            )
            return False

        return True

    def _log_request(
        self,
        model_name: str,
        is_primary: bool,
        success: bool,
        latency: float,
        cost: float = 0.0,
        error: Optional[str] = None
    ):
        """记录请求日志"""

        log_data = {
            'timestamp': datetime.now().isoformat(),
            'model': model_name,
            'is_primary': is_primary,
            'success': success,
            'latency': round(latency, 3),
            'cost': round(cost, 6)
        }

        if error:
            log_data['error'] = error

        # 这里可以写入日志文件或监控系统
        logger.info(f"Model request: {log_data}")

    def get_metrics(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """获取指标"""

        if model_name:
            if model_name not in self.metrics:
                return {}

            metrics = self.metrics[model_name]
            return {
                'model': model_name,
                'total_requests': metrics.total_requests,
                'successful_requests': metrics.successful_requests,
                'failed_requests': metrics.failed_requests,
                'success_rate': round(metrics.success_rate, 3),
                'avg_latency': round(metrics.avg_latency, 3),
                'total_cost': round(metrics.total_cost, 2),
                'avg_cost': round(metrics.avg_cost, 6),
                'consecutive_failures': metrics.consecutive_failures,
                'circuit_breaker_open': metrics.circuit_breaker_open
            }

        # 返回所有模型的指标
        return {
            name: {
                'total_requests': m.total_requests,
                'success_rate': round(m.success_rate, 3),
                'avg_latency': round(m.avg_latency, 3),
                'total_cost': round(m.total_cost, 2),
                'consecutive_failures': m.consecutive_failures,
                'circuit_breaker_open': m.circuit_breaker_open
            }
            for name, m in self.metrics.items()
        }

    def check_canary_health(self) -> Dict[str, Any]:
        """检查灰度健康状态"""

        if not self.canary_config.enabled:
            return {'enabled': False}

        canary_model = self.canary_config.canary_model
        if canary_model not in self.metrics:
            return {'enabled': True, 'status': 'no_data'}

        metrics = self.metrics[canary_model]

        # 检查是否达到最小请求数
        if metrics.total_requests < self.canary_config.min_requests:
            return {
                'enabled': True,
                'status': 'warming_up',
                'requests': metrics.total_requests,
                'min_requests': self.canary_config.min_requests
            }

        # 检查成功率
        success_rate = metrics.success_rate
        is_healthy = success_rate >= self.canary_config.success_threshold

        return {
            'enabled': True,
            'status': 'healthy' if is_healthy else 'unhealthy',
            'canary_model': canary_model,
            'success_rate': round(success_rate, 3),
            'threshold': self.canary_config.success_threshold,
            'total_requests': metrics.total_requests,
            'recommendation': 'promote' if is_healthy else 'rollback'
        }

    def promote_canary(self):
        """提升灰度模型为主模型"""

        if not self.canary_config.enabled:
            logger.warning("Canary is not enabled")
            return

        canary_model = self.canary_config.canary_model

        # 更新路由规则
        for task_type, rule in self.routing_rules.items():
            old_primary = rule.primary_model
            rule.primary_model = canary_model
            rule.fallback_models.insert(0, old_primary)

            logger.info(
                f"Promoted canary for {task_type}: "
                f"{old_primary} -> {canary_model}"
            )

        # 禁用灰度
        self.canary_config.enabled = False

        logger.info(f"Canary promoted: {canary_model}")

    def rollback_canary(self):
        """回滚灰度模型"""

        if not self.canary_config.enabled:
            logger.warning("Canary is not enabled")
            return

        # 直接禁用灰度
        self.canary_config.enabled = False

        logger.info(f"Canary rolled back: {self.canary_config.canary_model}")

    def reset_metrics(self):
        """重置指标"""
        for metrics in self.metrics.values():
            metrics.total_requests = 0
            metrics.successful_requests = 0
            metrics.failed_requests = 0
            metrics.total_latency = 0.0
            metrics.total_cost = 0.0
            metrics.consecutive_failures = 0
            metrics.circuit_breaker_open = False
            metrics.circuit_breaker_open_time = None

        logger.info("Metrics reset")
