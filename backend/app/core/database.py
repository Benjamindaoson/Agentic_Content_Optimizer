import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator
from app.core.config import get_settings

settings = get_settings()

# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,  # 连接前检查连接是否有效
    pool_recycle=3600,  # 1小时后回收连接
    pool_timeout=30,  # 连接超时时间
    echo=settings.DEBUG,
)

# 创建会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# 向后兼容别名
async_session_factory = AsyncSessionLocal

# 声明基类
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """初始化数据库"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """关闭数据库连接"""
    await engine.dispose()


async def check_db_ready(timeout_sec: int = 2) -> bool:
    """数据库就绪探针：执行轻量 SQL。"""
    try:
        async with AsyncSessionLocal() as session:
            await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=timeout_sec)
        return True
    except Exception:
        return False
