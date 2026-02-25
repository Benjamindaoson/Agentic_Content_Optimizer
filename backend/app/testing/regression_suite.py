"""
回归测试系统 - 确保系统改动不破坏现有功能
Regression Test Suite for Content Generation System
"""

from typing import Dict, Any, List, Optional
import logging
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TestCase:
    """测试用例"""
    id: str
    name: str
    description: str
    input: Dict[str, Any]
    expected_output: Optional[Dict[str, Any]] = None
    quality_threshold: float = 0.6
    tags: List[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class TestResult:
    """测试结果"""
    case_id: str
    case_name: str
    passed: bool
    quality_score: float
    output: Dict[str, Any]
    error: Optional[str] = None
    latency: float = 0.0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class RegressionReport:
    """回归测试报告"""
    version: str
    timestamp: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    avg_quality_score: float
    avg_latency: float
    test_results: List[TestResult]
    comparison_with_baseline: Optional[Dict[str, Any]] = None

    @property
    def pass_rate(self) -> float:
        if self.total_cases == 0:
            return 0.0
        return self.passed_cases / self.total_cases


class RegressionTestSuite:
    """
    回归测试套件

    功能：
    1. 加载固定测试集
    2. 执行回归测试
    3. 评估质量
    4. 对比基线
    5. 生成报告
    """

    def __init__(
        self,
        test_cases_path: str,
        baseline_path: Optional[str] = None
    ):
        """
        初始化回归测试套件

        Args:
            test_cases_path: 测试用例文件路径
            baseline_path: 基线结果文件路径
        """
        self.test_cases_path = Path(test_cases_path)
        self.baseline_path = Path(baseline_path) if baseline_path else None

        # 加载测试用例
        self.test_cases: List[TestCase] = []
        self._load_test_cases()

        # 加载基线
        self.baseline: Optional[RegressionReport] = None
        if self.baseline_path and self.baseline_path.exists():
            self._load_baseline()

        logger.info(
            f"Regression Test Suite initialized: "
            f"{len(self.test_cases)} test cases loaded"
        )

    def _load_test_cases(self):
        """加载测试用例"""

        if not self.test_cases_path.exists():
            logger.warning(f"Test cases file not found: {self.test_cases_path}")
            # 创建默认测试用例
            self._create_default_test_cases()
            return

        try:
            with open(self.test_cases_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for case_data in data.get('test_cases', []):
                test_case = TestCase(**case_data)
                self.test_cases.append(test_case)

            logger.info(f"Loaded {len(self.test_cases)} test cases")

        except Exception as e:
            logger.error(f"Failed to load test cases: {e}")
            self._create_default_test_cases()

    def _create_default_test_cases(self):
        """创建默认测试用例"""

        default_cases = [
            TestCase(
                id="tc_001",
                name="基础内容生成",
                description="测试基本的内容生成功能",
                input={
                    "topic": "短视频拍摄技巧",
                    "platform": "xiaohongshu",
                    "target_audience": {"age_range": [18, 35]}
                },
                quality_threshold=0.6,
                tags=["basic", "generation"]
            ),
            TestCase(
                id="tc_002",
                name="知识科普类内容",
                description="测试知识科普类内容生成",
                input={
                    "topic": "Python编程入门",
                    "platform": "douyin",
                    "target_audience": {"age_range": [20, 40], "interests": ["编程", "技术"]}
                },
                quality_threshold=0.65,
                tags=["knowledge", "education"]
            ),
            TestCase(
                id="tc_003",
                name="情绪共鸣类内容",
                description="测试情绪共鸣类内容生成",
                input={
                    "topic": "职场压力",
                    "platform": "xiaohongshu",
                    "target_audience": {"age_range": [25, 35], "pain_points": ["加班", "焦虑"]}
                },
                quality_threshold=0.7,
                tags=["emotion", "resonance"]
            ),
            TestCase(
                id="tc_004",
                name="产品推广类内容",
                description="测试产品推广类内容生成",
                input={
                    "topic": "护肤品推荐",
                    "platform": "xiaohongshu",
                    "target_audience": {"age_range": [20, 30], "interests": ["美妆", "护肤"]}
                },
                quality_threshold=0.65,
                tags=["product", "promotion"]
            ),
            TestCase(
                id="tc_005",
                name="长文本内容",
                description="测试长文本内容生成",
                input={
                    "topic": "如何提高工作效率：10个实用技巧",
                    "platform": "douyin",
                    "target_audience": {"age_range": [25, 45]}
                },
                quality_threshold=0.6,
                tags=["long_form", "tutorial"]
            )
        ]

        self.test_cases = default_cases

        # 保存到文件
        self._save_test_cases()

        logger.info(f"Created {len(default_cases)} default test cases")

    def _save_test_cases(self):
        """保存测试用例"""

        try:
            self.test_cases_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                'version': '1.0',
                'test_cases': [asdict(tc) for tc in self.test_cases]
            }

            with open(self.test_cases_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"Test cases saved to {self.test_cases_path}")

        except Exception as e:
            logger.error(f"Failed to save test cases: {e}")

    def _load_baseline(self):
        """加载基线"""

        try:
            with open(self.baseline_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 重建 TestResult 对象
            test_results = [TestResult(**r) for r in data.get('test_results', [])]

            self.baseline = RegressionReport(
                version=data['version'],
                timestamp=data['timestamp'],
                total_cases=data['total_cases'],
                passed_cases=data['passed_cases'],
                failed_cases=data['failed_cases'],
                avg_quality_score=data['avg_quality_score'],
                avg_latency=data['avg_latency'],
                test_results=test_results
            )

            logger.info(f"Baseline loaded: version={self.baseline.version}")

        except Exception as e:
            logger.error(f"Failed to load baseline: {e}")

    async def run_regression(
        self,
        system_version: str,
        generation_func: Any,  # 生成函数
        evaluation_func: Any,  # 评估函数
        tags: Optional[List[str]] = None
    ) -> RegressionReport:
        """
        运行回归测试

        Args:
            system_version: 系统版本
            generation_func: 内容生成函数
            evaluation_func: 质量评估函数
            tags: 只运行特定标签的测试用例

        Returns:
            RegressionReport
        """

        logger.info(f"Starting regression test for version: {system_version}")

        # 过滤测试用例
        if tags:
            test_cases = [
                tc for tc in self.test_cases
                if any(tag in tc.tags for tag in tags)
            ]
        else:
            test_cases = self.test_cases

        # 执行测试
        test_results = []

        for i, test_case in enumerate(test_cases, 1):
            logger.info(f"Running test case {i}/{len(test_cases)}: {test_case.name}")

            result = await self._run_single_test(
                test_case=test_case,
                generation_func=generation_func,
                evaluation_func=evaluation_func
            )

            test_results.append(result)

        # 统计
        passed_cases = sum(1 for r in test_results if r.passed)
        failed_cases = len(test_results) - passed_cases
        avg_quality = np.mean([r.quality_score for r in test_results])
        avg_latency = np.mean([r.latency for r in test_results])

        # 对比基线
        comparison = None
        if self.baseline:
            comparison = self._compare_with_baseline(test_results)

        # 生成报告
        report = RegressionReport(
            version=system_version,
            timestamp=datetime.now().isoformat(),
            total_cases=len(test_results),
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            avg_quality_score=round(avg_quality, 3),
            avg_latency=round(avg_latency, 3),
            test_results=test_results,
            comparison_with_baseline=comparison
        )

        logger.info(
            f"Regression test completed: "
            f"pass_rate={report.pass_rate:.1%}, "
            f"avg_quality={report.avg_quality_score:.3f}"
        )

        return report

    async def _run_single_test(
        self,
        test_case: TestCase,
        generation_func: Any,
        evaluation_func: Any
    ) -> TestResult:
        """运行单个测试用例"""

        import time

        start_time = time.time()

        try:
            # 生成内容
            output = await generation_func(test_case.input)

            # 评估质量
            quality_score = await evaluation_func(output, test_case.input)

            # 判断是否通过
            passed = quality_score >= test_case.quality_threshold

            latency = time.time() - start_time

            return TestResult(
                case_id=test_case.id,
                case_name=test_case.name,
                passed=passed,
                quality_score=round(quality_score, 3),
                output=output,
                latency=round(latency, 3)
            )

        except Exception as e:
            latency = time.time() - start_time

            logger.error(f"Test case {test_case.id} failed: {e}")

            return TestResult(
                case_id=test_case.id,
                case_name=test_case.name,
                passed=False,
                quality_score=0.0,
                output={},
                error=str(e),
                latency=round(latency, 3)
            )

    def _compare_with_baseline(
        self,
        current_results: List[TestResult]
    ) -> Dict[str, Any]:
        """对比基线"""

        if not self.baseline:
            return {}

        # 按 case_id 匹配
        baseline_map = {r.case_id: r for r in self.baseline.test_results}
        current_map = {r.case_id: r for r in current_results}

        # 对比
        improvements = []
        regressions = []
        unchanged = []

        for case_id in current_map:
            if case_id not in baseline_map:
                continue

            baseline_score = baseline_map[case_id].quality_score
            current_score = current_map[case_id].quality_score

            diff = current_score - baseline_score

            if abs(diff) < 0.05:  # 变化小于 5% 视为不变
                unchanged.append(case_id)
            elif diff > 0:
                improvements.append({
                    'case_id': case_id,
                    'case_name': current_map[case_id].case_name,
                    'baseline_score': baseline_score,
                    'current_score': current_score,
                    'improvement': round(diff, 3)
                })
            else:
                regressions.append({
                    'case_id': case_id,
                    'case_name': current_map[case_id].case_name,
                    'baseline_score': baseline_score,
                    'current_score': current_score,
                    'regression': round(abs(diff), 3)
                })

        # 整体对比
        baseline_avg = self.baseline.avg_quality_score
        current_avg = np.mean([r.quality_score for r in current_results])
        overall_diff = current_avg - baseline_avg

        return {
            'baseline_version': self.baseline.version,
            'baseline_avg_quality': baseline_avg,
            'current_avg_quality': round(current_avg, 3),
            'overall_diff': round(overall_diff, 3),
            'improvements': improvements,
            'regressions': regressions,
            'unchanged': len(unchanged),
            'recommendation': 'approve' if overall_diff >= -0.05 else 'review'
        }

    def save_report(self, report: RegressionReport, output_path: str):
        """保存报告"""

        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # 转换为可序列化的格式
            data = {
                'version': report.version,
                'timestamp': report.timestamp,
                'total_cases': report.total_cases,
                'passed_cases': report.passed_cases,
                'failed_cases': report.failed_cases,
                'pass_rate': round(report.pass_rate, 3),
                'avg_quality_score': report.avg_quality_score,
                'avg_latency': report.avg_latency,
                'test_results': [asdict(r) for r in report.test_results],
                'comparison_with_baseline': report.comparison_with_baseline
            }

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"Report saved to {output_path}")

        except Exception as e:
            logger.error(f"Failed to save report: {e}")

    def set_as_baseline(self, report: RegressionReport):
        """将当前报告设为基线"""

        if not self.baseline_path:
            logger.warning("Baseline path not set")
            return

        self.save_report(report, str(self.baseline_path))
        self.baseline = report

        logger.info(f"Baseline updated: version={report.version}")
