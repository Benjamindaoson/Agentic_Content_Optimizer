"""
生产监控系统

实时监控多样性评分和 Thompson Sampling 的关键指标
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from datetime import datetime
import numpy as np
from app.monitoring.alert_notifier import AlertNotifier

logger = logging.getLogger(__name__)


class DuplicationMonitor:
    """重复率监控器"""

    def __init__(self, threshold: float = 0.92):
        self.threshold = threshold
        self.daily_stats = defaultdict(lambda: {'total': 0, 'duplicates': 0})

    def record(self, similarity: float, date: Optional[str] = None):
        """记录相似度"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        self.daily_stats[date]['total'] += 1
        if similarity >= self.threshold:
            self.daily_stats[date]['duplicates'] += 1

    def get_duplication_rate(self, date: Optional[str] = None) -> float:
        """获取重复率"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        stats = self.daily_stats[date]
        if stats['total'] == 0:
            return 0.0
        return stats['duplicates'] / stats['total']

    def check_alert(self, warning_threshold: float = 0.3, critical_threshold: float = 0.5) -> Optional[str]:
        """检查告警"""
        rate = self.get_duplication_rate()

        if rate >= critical_threshold:
            return f"CRITICAL: 重复率 {rate:.2%} >= {critical_threshold:.2%}"
        elif rate >= warning_threshold:
            return f"WARNING: 重复率 {rate:.2%} >= {warning_threshold:.2%}"

        return None


class EntropyMonitor:
    """策略熵监控器"""

    def __init__(self):
        self.strategy_counts = defaultdict(int)

    def record(self, strategy: Tuple):
        """记录策略"""
        self.strategy_counts[strategy] += 1

    def calculate_entropy(self) -> float:
        """计算策略熵"""
        total = sum(self.strategy_counts.values())
        if total == 0:
            return 0.0

        probs = [count / total for count in self.strategy_counts.values()]
        entropy = -sum(p * np.log(p + 1e-12) for p in probs)

        # 归一化到 [0, 1]
        max_entropy = np.log(len(self.strategy_counts)) if len(self.strategy_counts) > 0 else 1.0
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0.0

        return normalized_entropy

    def calculate_layer_entropy(
        self,
        hook_counts: Dict,
        body_counts: Dict,
        cta_counts: Dict
    ) -> Dict[str, float]:
        """计算各层熵"""
        def calc_entropy(counts: Dict) -> float:
            total = sum(counts.values())
            if total == 0:
                return 0.0
            probs = [c / total for c in counts.values()]
            entropy = -sum(p * np.log(p + 1e-12) for p in probs)
            max_entropy = np.log(len(counts)) if len(counts) > 0 else 1.0
            return entropy / max_entropy if max_entropy > 0 else 0.0

        return {
            'hook_entropy': calc_entropy(hook_counts),
            'body_entropy': calc_entropy(body_counts),
            'cta_entropy': calc_entropy(cta_counts),
            'triplet_entropy': self.calculate_entropy()
        }

    def check_alert(self, warning_threshold: float = 0.3, critical_threshold: float = 0.1) -> Optional[str]:
        """检查告警"""
        entropy = self.calculate_entropy()

        if entropy <= critical_threshold:
            return f"CRITICAL: 策略熵 {entropy:.4f} <= {critical_threshold}"
        elif entropy <= warning_threshold:
            return f"WARNING: 策略熵 {entropy:.4f} <= {warning_threshold}"

        return None


class ExplorationMonitor:
    """探索率监控器"""

    def __init__(self):
        self.explored_actions = set()
        self.total_actions = 0

    def record(self, action: Tuple, is_new: bool = False):
        """记录动作"""
        self.total_actions += 1
        if is_new or action not in self.explored_actions:
            self.explored_actions.add(action)

    def calculate_exploration_rate(self, total_possible_actions: int) -> float:
        """计算探索率"""
        if total_possible_actions == 0:
            return 0.0
        return len(self.explored_actions) / total_possible_actions

    def check_alert(
        self,
        total_possible_actions: int,
        low_threshold: float = 0.2,
        high_threshold: float = 0.8
    ) -> Optional[str]:
        """检查告警"""
        rate = self.calculate_exploration_rate(total_possible_actions)

        if rate <= low_threshold:
            return f"WARNING: 探索率 {rate:.2%} <= {low_threshold:.2%}（探索不足）"
        elif rate >= high_threshold:
            return f"INFO: 探索率 {rate:.2%} >= {high_threshold:.2%}（收敛慢）"

        return None


class RewardDistributionMonitor:
    """奖励分布监控器"""

    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.components_history = {
            'quality': [],
            'predicted': [],
            'diversity': [],
            'geo': [],
            'innovation': [],
            'total': []
        }

    def record(self, reward_components: Dict[str, float]):
        """记录奖励"""
        for component, value in reward_components.items():
            if component in self.components_history:
                self.components_history[component].append(value)

                # 保持窗口大小
                if len(self.components_history[component]) > self.window_size:
                    self.components_history[component] = self.components_history[component][-self.window_size:]

    def get_statistics(self) -> Dict[str, Dict[str, float]]:
        """获取统计信息"""
        stats = {}
        for component, values in self.components_history.items():
            if not values:
                continue

            stats[component] = {
                'mean': float(np.mean(values)),
                'std': float(np.std(values)),
                'min': float(np.min(values)),
                'max': float(np.max(values)),
                'p25': float(np.percentile(values, 25)),
                'p50': float(np.percentile(values, 50)),
                'p75': float(np.percentile(values, 75))
            }

        return stats

    def check_distribution_health(
        self,
        std_min: float = 0.05,
        std_max: float = 0.5
    ) -> Dict[str, bool]:
        """检查分布健康度"""
        stats = self.get_statistics()
        health = {}

        for component, stat in stats.items():
            # 检查标准差是否在合理范围
            std_healthy = std_min < stat['std'] < std_max

            # 检查均值是否在合理范围
            mean_healthy = 0.0 <= stat['mean'] <= 2.0

            health[component] = std_healthy and mean_healthy

        return health

    def check_alert(self, std_min: float = 0.05, std_max: float = 0.5) -> List[str]:
        """检查告警"""
        health = self.check_distribution_health(std_min, std_max)
        alerts = []

        for component, is_healthy in health.items():
            if not is_healthy:
                stats = self.get_statistics()[component]
                alerts.append(
                    f"WARNING: {component} 分布异常 "
                    f"(mean={stats['mean']:.3f}, std={stats['std']:.3f})"
                )

        return alerts


class TopKStabilityMonitor:
    """Top-K 策略稳定性监控器"""

    def __init__(self, k: int = 10):
        self.k = k
        self.daily_topk = {}

    def record(self, date: str, top_strategies: List[Tuple]):
        """记录每日 Top-K"""
        self.daily_topk[date] = set(s[0] if isinstance(s, tuple) else s for s in top_strategies[:self.k])

    def calculate_stability(self, date1: str, date2: str) -> float:
        """计算两天的重合度"""
        if date1 not in self.daily_topk or date2 not in self.daily_topk:
            return 0.0

        set1 = self.daily_topk[date1]
        set2 = self.daily_topk[date2]

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    def check_alert(self, threshold: float = 0.3) -> Optional[str]:
        """检查告警"""
        dates = sorted(self.daily_topk.keys())
        if len(dates) < 2:
            return None

        # 检查最近两天的稳定性
        stability = self.calculate_stability(dates[-2], dates[-1])

        if stability < threshold:
            return f"WARNING: Top-{self.k} 稳定性 {stability:.2%} < {threshold:.2%}（策略漂移）"

        return None


class ProductionMonitor:
    """
    生产监控系统

    集成所有监控器，提供统一接口
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化

        Args:
            config: 监控配置
        """
        config = config or {}

        # 创建监控器
        self.duplication_monitor = DuplicationMonitor(
            threshold=config.get('duplication_threshold', 0.92)
        )

        self.entropy_monitor = EntropyMonitor()

        self.exploration_monitor = ExplorationMonitor()

        self.reward_monitor = RewardDistributionMonitor(
            window_size=config.get('reward_window_size', 1000)
        )

        self.topk_monitor = TopKStabilityMonitor(
            k=config.get('topk_k', 10)
        )

        # 告警阈值
        self.alert_config = {
            'duplication_warning': config.get('duplication_warning', 0.3),
            'duplication_critical': config.get('duplication_critical', 0.5),
            'entropy_warning': config.get('entropy_warning', 0.3),
            'entropy_critical': config.get('entropy_critical', 0.1),
            'exploration_low': config.get('exploration_low', 0.2),
            'exploration_high': config.get('exploration_high', 0.8),
            'reward_std_min': config.get('reward_std_min', 0.05),
            'reward_std_max': config.get('reward_std_max', 0.5),
            'topk_stability': config.get('topk_stability', 0.3)
        }
        self.notifier = AlertNotifier()

        logger.info("✅ ProductionMonitor 初始化完成")

    def record_generation(
        self,
        similarity: float,
        strategy: Tuple,
        reward_components: Dict[str, float],
        is_new_action: bool = False
    ):
        """
        记录一次生成

        Args:
            similarity: 与历史的最大相似度
            strategy: 使用的策略 (hook, body, cta)
            reward_components: 奖励分解
            is_new_action: 是否是新动作
        """
        self.duplication_monitor.record(similarity)
        self.entropy_monitor.record(strategy)
        self.exploration_monitor.record(strategy, is_new_action)
        self.reward_monitor.record(reward_components)

    def record_daily_topk(self, date: str, top_strategies: List[Tuple]):
        """记录每日 Top-K"""
        self.topk_monitor.record(date, top_strategies)

    def get_all_metrics(self) -> Dict[str, Any]:
        """获取所有指标"""
        return {
            'duplication_rate': self.duplication_monitor.get_duplication_rate(),
            'strategy_entropy': self.entropy_monitor.calculate_entropy(),
            'exploration_rate': self.exploration_monitor.calculate_exploration_rate(400),  # 假设 400 种动作
            'reward_statistics': self.reward_monitor.get_statistics(),
            'reward_health': self.reward_monitor.check_distribution_health(
                self.alert_config['reward_std_min'],
                self.alert_config['reward_std_max']
            )
        }

    def check_all_alerts(self, total_possible_actions: int = 400) -> List[str]:
        """检查所有告警"""
        alerts = []

        # 重复率告警
        alert = self.duplication_monitor.check_alert(
            self.alert_config['duplication_warning'],
            self.alert_config['duplication_critical']
        )
        if alert:
            alerts.append(alert)

        # 熵告警
        alert = self.entropy_monitor.check_alert(
            self.alert_config['entropy_warning'],
            self.alert_config['entropy_critical']
        )
        if alert:
            alerts.append(alert)

        # 探索率告警
        alert = self.exploration_monitor.check_alert(
            total_possible_actions,
            self.alert_config['exploration_low'],
            self.alert_config['exploration_high']
        )
        if alert:
            alerts.append(alert)

        # Reward 分布告警
        reward_alerts = self.reward_monitor.check_alert(
            self.alert_config['reward_std_min'],
            self.alert_config['reward_std_max']
        )
        alerts.extend(reward_alerts)

        # Top-K 稳定性告警
        alert = self.topk_monitor.check_alert(self.alert_config['topk_stability'])
        if alert:
            alerts.append(alert)

        return alerts

    def get_dashboard_data(self) -> Dict[str, Any]:
        """获取仪表板数据"""
        metrics = self.get_all_metrics()
        alerts = self.check_all_alerts()

        return {
            'timestamp': datetime.now().isoformat(),
            'metrics': metrics,
            'alerts': alerts,
            'alert_count': {
                'critical': sum(1 for a in alerts if 'CRITICAL' in a),
                'warning': sum(1 for a in alerts if 'WARNING' in a),
                'info': sum(1 for a in alerts if 'INFO' in a)
            }
        }

    def dispatch_alerts(self, total_possible_actions: int = 400) -> Dict[str, Any]:
        """发送告警到外部渠道（Slack/PagerDuty）。"""
        alerts = self.check_all_alerts(total_possible_actions=total_possible_actions)
        result = self.notifier.notify(alerts)
        return {
            "alerts": alerts,
            "notify_result": result,
        }
