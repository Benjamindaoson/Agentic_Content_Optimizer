"""数据工程模块（延迟导入，避免历史依赖在启动期阻塞）。"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.data.data_engineering.synthetic_data_generator import (
        get_synthetic_data_generator,
        SyntheticDataGenerator,
        SyntheticSample,
        PreferencePair,
    )
    from app.data.data_engineering.agent_benchmark import (
        get_agent_benchmark,
        AgentBenchmark,
        BenchmarkTask,
        BenchmarkResult,
        BenchmarkReport,
    )


def __getattr__(name: str):
    if name in {
        "get_synthetic_data_generator",
        "SyntheticDataGenerator",
        "SyntheticSample",
        "PreferencePair",
    }:
        from app.data.data_engineering.synthetic_data_generator import (
            get_synthetic_data_generator,
            SyntheticDataGenerator,
            SyntheticSample,
            PreferencePair,
        )
        mapping = {
            "get_synthetic_data_generator": get_synthetic_data_generator,
            "SyntheticDataGenerator": SyntheticDataGenerator,
            "SyntheticSample": SyntheticSample,
            "PreferencePair": PreferencePair,
        }
        return mapping[name]
    if name in {
        "get_agent_benchmark",
        "AgentBenchmark",
        "BenchmarkTask",
        "BenchmarkResult",
        "BenchmarkReport",
    }:
        from app.data.data_engineering.agent_benchmark import (
            get_agent_benchmark,
            AgentBenchmark,
            BenchmarkTask,
            BenchmarkResult,
            BenchmarkReport,
        )
        mapping = {
            "get_agent_benchmark": get_agent_benchmark,
            "AgentBenchmark": AgentBenchmark,
            "BenchmarkTask": BenchmarkTask,
            "BenchmarkResult": BenchmarkResult,
            "BenchmarkReport": BenchmarkReport,
        }
        return mapping[name]
    raise AttributeError(name)


__all__ = [
    "get_synthetic_data_generator",
    "SyntheticDataGenerator",
    "SyntheticSample",
    "PreferencePair",
    "get_agent_benchmark",
    "AgentBenchmark",
    "BenchmarkTask",
    "BenchmarkResult",
    "BenchmarkReport",
]
