"""
测试配置和 Fixtures
Test Configuration and Fixtures
"""

import pytest
import asyncio
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.core.database import Base
from app.core.redis import RedisClient


# ==================== 测试配置 ====================

@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """测试环境配置"""
    return Settings(
        ENVIRONMENT="test",
        DEBUG=True,
        DATABASE_URL="postgresql://test:test@localhost:5432/test_growth_flywheel",
        REDIS_URL="redis://localhost:6379/1",
        JWT_SECRET="test-jwt-secret-key-for-testing-only-32-chars",
        CORS_ORIGINS="http://localhost:3000",
        ANTHROPIC_API_KEY="test-key",
        OPENAI_API_KEY="test-key",
        QWEN_API_KEY="test-key",
        LANGCHAIN_API_KEY="test-key"
    )


# ==================== 事件循环 ====================

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ==================== 数据库 Fixtures ====================

@pytest.fixture(scope="session")
async def test_engine(test_settings: Settings):
    """测试数据库引擎"""
    engine = create_async_engine(
        test_settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool,
        echo=False
    )

    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # 清理所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """测试数据库会话"""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as session:
        yield session
        await session.rollback()


# ==================== Redis Fixtures ====================

@pytest.fixture
async def redis_client(test_settings: Settings) -> AsyncGenerator[RedisClient, None]:
    """测试 Redis 客户端"""
    client = RedisClient(test_settings.REDIS_URL)
    await client.connect()

    yield client

    # 清理测试数据
    await client.flushdb()
    await client.close()


# ==================== Mock Fixtures ====================

@pytest.fixture
def mock_llm_response():
    """Mock LLM 响应"""
    return {
        "content": "这是一个测试响应",
        "model": "test-model",
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        }
    }


@pytest.fixture
def mock_rag_documents():
    """Mock RAG 检索文档"""
    return [
        {
            "id": "doc1",
            "text": "这是第一个测试文档",
            "score": 0.95,
            "metadata": {"source": "test"}
        },
        {
            "id": "doc2",
            "text": "这是第二个测试文档",
            "score": 0.85,
            "metadata": {"source": "test"}
        }
    ]


@pytest.fixture
def mock_content_data():
    """Mock 内容数据"""
    return {
        "topic": "AI 写作",
        "platform": "xiaohongshu",
        "style": "professional",
        "target_audience": "技术爱好者"
    }


@pytest.fixture
def mock_action_data():
    """Mock 动作数据"""
    return {
        "hook": "你知道吗？",
        "body": "AI 写作正在改变内容创作",
        "cta": "关注我了解更多"
    }


# ==================== 测试工具函数 ====================

@pytest.fixture
def assert_almost_equal():
    """断言浮点数近似相等"""
    def _assert(a: float, b: float, tolerance: float = 1e-6):
        assert abs(a - b) < tolerance, f"{a} != {b} (tolerance={tolerance})"
    return _assert


@pytest.fixture
def create_test_user(db_session: AsyncSession):
    """创建测试用户"""
    async def _create(username: str = "testuser", email: str = "test@example.com"):
        from app.models.user import User
        user = User(username=username, email=email)
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user
    return _create


@pytest.fixture
def create_test_content(db_session: AsyncSession):
    """创建测试内容"""
    async def _create(topic: str = "测试话题", platform: str = "xiaohongshu"):
        from app.models.content import Content
        content = Content(topic=topic, platform=platform)
        db_session.add(content)
        await db_session.commit()
        await db_session.refresh(content)
        return content
    return _create
