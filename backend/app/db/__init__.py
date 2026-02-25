"""Backward compatibility layer for legacy `app.db.*` imports.

新代码应优先使用：
- `app.core.database`（异步会话）
- `app.ml.training.schemas` / 领域模块中的模型
"""

from app.core.database import Base as AsyncBase  # 新异步基类
from app.core.database import AsyncSessionLocal, get_db as get_async_db

# 兼容旧同步路径（大量历史模块仍在引用）
from app.db.database import (  # noqa: F401
    engine,
    get_db,
    get_db_session,
    SessionLocal,
    init_db,
    drop_db,
    check_db_health,
)
from app.db.models import (  # noqa: F401
    Base,
    XHSNote,
    XHSMetrics,
    XHSCover,
    XHSAnalysis,
    Pattern,
    PatternSample,
    Generation,
    OnlineMetrics,
    GRPORun,
    CrawlTask,
)

# 向后兼容别名
async_session_factory = AsyncSessionLocal

__all__ = [
    "AsyncBase",
    "AsyncSessionLocal",
    "get_async_db",
    "engine",
    "get_db",
    "get_db_session",
    "SessionLocal",
    "init_db",
    "drop_db",
    "check_db_health",
    "Base",
    "XHSNote",
    "XHSMetrics",
    "XHSCover",
    "XHSAnalysis",
    "Pattern",
    "PatternSample",
    "Generation",
    "OnlineMetrics",
    "GRPORun",
    "CrawlTask",
    "async_session_factory",
]
