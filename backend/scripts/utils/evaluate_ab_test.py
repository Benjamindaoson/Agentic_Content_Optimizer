"""
A/B 实验评估脚本
对比 Baseline (纯 SFT) vs Experiment (GRPO 优化)
"""

import json
import logging
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass
import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ABTestResult:
    """A/B 测试结果"""
    metric_name: str
    baseline_mean: float
    experiment_mean: float
    improvement: float
    p_value: float
    is_significant: bool


class ABTestEvaluator:
    """A/B 测试评估器"""

    def __init__(
        self,
        baseline_path: str,
        experiment_path: str,
        output_dir: str = "./results/ab_test"
    ):
        self.baseline_path = Path(baseline_path)
        self.experiment_path = Path(experiment_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 加载数据
        self.baseline_data = self._load_data(self.baseline_path)
        self.experiment_data = self._load_data(self.experiment_path)

        logger.info(f"Loaded {len(self.baseline_data)} baseline samples")
        logger.info(f"Loaded {len(self.experiment_data)} experiment samples")

    def _load_data(self, path: Path) -> List[Dict]:
        """加载数据"""
        if path.suffix == ".json":
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        elif path.suffix == ".jsonl":
            data = []
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    data.append(json.loads(line))
            return data
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")

    def evaluate_high_score_coverage(self) -> ABTestResult:
        """
        评估指标1: 高分区覆盖率提升
        计算评分 >= 0.8 的内容占比
        """
        logger.info("Evaluating high score coverage...")

        # Baseline
        baseline_scores = [item.get("overall_score", 0) for item in self.baseline_data]
        baseline_high_score = sum(1 for score in baseline_scores if score >= 0.8)
        baseline_coverage = baseline_high_score / len(baseline_scores)

        # Experiment
        experiment_scores = [item.get("overall_score", 0) for item in self.experiment_data]
        experiment_high_score = sum(1 for score in experiment_scores if score >= 0.8)
        experiment_coverage = experiment_high_score / len(experiment_scores)

        # 提升
        improvement = (experiment_coverage - baseline_coverage) / baseline_coverage * 100

        # 统计检验（卡方检验）
        contingency_table = [
            [baseline_high_score, len(baseline_scores) - baseline_high_score],
            [experiment_high_score, len(experiment_scores) - experiment_high_score]
        ]
        chi2, p_value = stats.chi2_contingency(contingency_table)[:2]

        return ABTestResult(
            metric_name="High Score Coverage (>= 0.8)",
            baseline_mean=baseline_coverage,
            experiment_mean=experiment_coverage,
            improvement=improvement,
            p_value=p_value,
            is_significant=p_value < 0.05
        )

    def evaluate_geo_success_rate(self) -> ABTestResult:
        """
        评估指标2: GEO 引用成功率
        计算 GEO 评分 >= 0.7 的内容占比
        """
        logger.info("Evaluating GEO success rate...")

        # Baseline
        baseline_geo_scores = [item.get("geo_score", 0) for item in self.baseline_data]
        baseline_success = sum(1 for score in baseline_geo_scores if score >= 0.7)
        baseline_rate = baseline_success / len(baseline_geo_scores)

        # Experiment
        experiment_geo_scores = [item.get("geo_score", 0) for item in self.experiment_data]
        experiment_success = sum(1 for score in experiment_geo_scores if score >= 0.7)
        experiment_rate = experiment_success / len(experiment_geo_scores)

        # 提升
        improvement = (experiment_rate - baseline_rate) / baseline_rate * 100

        # 统计检验
        contingency_table = [
            [baseline_success, len(baseline_geo_scores) - baseline_success],
            [experiment_success, len(experiment_geo_scores) - experiment_success]
        ]
        chi2, p_value = stats.chi2_contingency(contingency_table)[:2]

        return ABTestResult(
            metric_name="GEO Success Rate (>= 0.7)",
            baseline_mean=baseline_rate,
            experiment_mean=experiment_rate,
            improvement=improvement,
            p_value=p_value,
            is_significant=p_value < 0.05
        )

    def evaluate_structure_diversity(self) -> ABTestResult:
        """
        评估指标3: 结构多样性（Hook/Body/CTA 熵）
        计算动作组合的熵
        """
        logger.info("Evaluating structure diversity...")

        def calculate_entropy(data: List[Dict]) -> float:
            """计算熵"""
            # 统计动作组合
            action_counts = {}
            for item in data:
                action = item.get("action", {})
                key = f"{action.get('hook', '')}_{action.get('body', '')}_{action.get('cta', '')}"
                action_counts[key] = action_counts.get(key, 0) + 1

            # 计算概率
            total = sum(action_counts.values())
            probs = [count / total for count in action_counts.values()]

            # 计算熵
            entropy = -sum(p * np.log2(p) for p in probs if p > 0)
            return entropy

        # Baseline
        baseline_entropy = calculate_entropy(self.baseline_data)

        # Experiment
        experiment_entropy = calculate_entropy(self.experiment_data)

        # 提升
        improvement = (experiment_entropy - baseline_entropy) / baseline_entropy * 100

        # 统计检验（Bootstrap）
        def bootstrap_entropy(data, n_bootstrap=1000):
            entropies = []
            for _ in range(n_bootstrap):
                sample = np.random.choice(len(data), size=len(data), replace=True)
                sample_data = [data[i] for i in sample]
                entropies.append(calculate_entropy(sample_data))
            return entropies

        baseline_entropies = bootstrap_entropy(self.baseline_data)
        experiment_entropies = bootstrap_entropy(self.experiment_data)

        # t 检验
        t_stat, p_value = stats.ttest_ind(experiment_entropies, baseline_entropies)

        return ABTestResult(
            metric_name="Structure Diversity (Entropy)",
            baseline_mean=baseline_entropy,
            experiment_mean=experiment_entropy,
            improvement=improvement,
            p_value=p_value,
            is_significant=p_value < 0.05
        )

    def run_all_tests(self) -> List[ABTestResult]:
        """运行所有测试"""
        logger.info("=" * 60)
        logger.info("Running A/B Tests")
        logger.info("=" * 60)

        results = []

        # 1. 高分区覆盖率
        result1 = self.evaluate_high_score_coverage()
        results.append(result1)

        # 2. GEO 引用成功率
        result2 = self.evaluate_geo_success_rate()
        results.append(result2)

        # 3. 结构多样性
        result3 = self.evaluate_structure_diversity()
        results.append(result3)

        return results

    def generate_report(self, results: List[ABTestResult]):
        """生成报告"""
        logger.info("=" * 60)
        logger.info("A/B Test Results")
        logger.info("=" * 60)

        for result in results:
            logger.info(f"\n{result.metric_name}:")
            logger.info(f"  Baseline:    {result.baseline_mean:.4f}")
            logger.info(f"  Experiment:  {result.experiment_mean:.4f}")
            logger.info(f"  Improvement: {result.improvement:+.2f}%")
            logger.info(f"  P-value:     {result.p_value:.4f}")
            logger.info(f"  Significant: {'✅ Yes' if result.is_significant else '❌ No'}")

        # 保存为 JSON
        report_path = self.output_dir / "ab_test_results.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(
                [
                    {
                        "metric": r.metric_name,
                        "baseline": r.baseline_mean,
                        "experiment": r.experiment_mean,
                        "improvement": r.improvement,
                        "p_value": r.p_value,
                        "significant": r.is_significant
                    }
                    for r in results
                ],
                f,
                indent=2,
                ensure_ascii=False
            )

        logger.info(f"\nReport saved to: {report_path}")

    def plot_results(self, results: List[ABTestResult]):
        """绘制结果图表"""
        logger.info("Generating plots...")

        # 设置样式
        sns.set_style("whitegrid")
        plt.rcParams['font.sans-serif'] = ['SimHei']  # 中文字体
        plt.rcParams['axes.unicode_minus'] = False

        # 创建图表
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))

        for i, result in enumerate(results):
            ax = axes[i]

            # 条形图
            categories = ['Baseline', 'Experiment']
            values = [result.baseline_mean, result.experiment_mean]
            colors = ['#3498db', '#2ecc71']

            bars = ax.bar(categories, values, color=colors, alpha=0.7)

            # 添加数值标签
            for bar in bars:
                height = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2.,
                    height,
                    f'{height:.4f}',
                    ha='center',
                    va='bottom'
                )

            # 添加提升百分比
            ax.text(
                0.5,
                max(values) * 0.9,
                f'Improvement: {result.improvement:+.2f}%',
                ha='center',
                fontsize=10,
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5)
            )

            # 标题和标签
            ax.set_title(result.metric_name, fontsize=12, fontweight='bold')
            ax.set_ylabel('Score', fontsize=10)

            # 显著性标记
            if result.is_significant:
                ax.text(
                    0.5,
                    max(values) * 0.8,
                    '✅ Significant (p < 0.05)',
                    ha='center',
                    fontsize=9,
                    color='green'
                )

        plt.tight_layout()

        # 保存图表
        plot_path = self.output_dir / "ab_test_results.png"
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        logger.info(f"Plot saved to: {plot_path}")

        plt.close()


def main():
    """主函数"""
    # 创建评估器
    evaluator = ABTestEvaluator(
        baseline_path="./results/baseline/generated_contents.jsonl",
        experiment_path="./results/experiment/generated_contents.jsonl",
        output_dir="./results/ab_test"
    )

    # 运行测试
    results = evaluator.run_all_tests()

    # 生成报告
    evaluator.generate_report(results)

    # 绘制图表
    evaluator.plot_results(results)

    logger.info("\nA/B Test evaluation completed!")


if __name__ == "__main__":
    main()
