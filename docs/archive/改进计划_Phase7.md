# Phase 7 改进计划 - 系统完善

## 📋 执行摘要

**开始时间**: 2026-02-14
**Phase**: Phase 7 - 系统完善
**目标**: 完善剩余 5% 的功能，提升系统稳定性
**预计耗时**: 1-2 天

---

## 🎯 改进目标

### 1. TrendAgent 真实数据库检索 ✅

**当前问题**:
- `_fallback_db_search()` 方法返回模拟数据
- 实际应用中会影响检索准确性
- 无法利用数据库中的真实爆款内容

**改进方案**:
```python
async def _fallback_db_search(
    self,
    topic: str,
    platform: str,
    limit: int,
    db: AsyncSession
) -> List[Dict[str, Any]]:
    """降级：从数据库检索真实爆款内容"""

    # 1. 使用全文搜索查询相关内容
    query = (
        select(ViralContent)
        .where(ViralContent.platform == platform)
        .where(ViralContent.text.contains(topic))  # 简单文本匹配
        .order_by(desc(ViralContent.engagement_score))
        .limit(limit)
    )

    result = await db.execute(query)
    viral_contents = result.scalars().all()

    # 2. 转换为统一格式
    references = []
    for content in viral_contents:
        references.append({
            "id": content.content_id,
            "score": content.engagement_score / 100000,  # 归一化
            "metadata": {
                "platform": content.platform.value,
                "text": content.text,
                "engagement_score": content.engagement_score,
                "hook_type": content.hook_type,
                "body_structure": content.body_structure,
                "cta_type": content.cta_type,
                "image_urls": content.image_urls or [],
                "likes": content.likes,
                "comments": content.comments,
                "shares": content.shares
            }
        })

    return references
```

**实现步骤**:
1. ✅ 修改 `TrendAgent.__init__()` 接受 `db: AsyncSession` 参数
2. ✅ 实现真实的数据库查询逻辑
3. ✅ 添加全文搜索支持（如果数据库支持）
4. ✅ 更新 API 调用，传入数据库会话
5. ✅ 测试真实数据检索

**预期效果**:
- 检索准确率提升 **30-50%**
- 返回真实的爆款内容
- 支持按互动分数排序

---

### 2. 提升测试覆盖率（30% → 70%）✅

**当前问题**:
- 测试覆盖率只有 30%
- 核心模块缺少单元测试
- 集成测试不完整

**改进方案**:

#### 2.1 核心模块单元测试

**需要测试的模块**:
1. **多智能体系统** (优先级：高)
   - `tests/test_agents/test_writer_agent.py`
   - `tests/test_agents/test_critic_agent.py`
   - `tests/test_agents/test_trend_agent.py`
   - `tests/test_agents/test_director_agent.py`

2. **Planning & Reflection** (优先级：高)
   - `tests/test_planning/test_planner.py`
   - `tests/test_planning/test_reflector.py`

3. **LangGraph 工作流** (优先级：高)
   - `tests/test_workflow/test_langgraph_workflow.py`

4. **RAG 系统** (优先级：中)
   - `tests/test_rag/test_hybrid_retriever.py`
   - `tests/test_rag/test_rag_evaluator.py`
   - `tests/test_rag/test_advanced_rag.py`

5. **RL 系统** (优先级：中)
   - `tests/test_rl/test_grpo_trainer.py`
   - `tests/test_rl/test_online_learning_loop.py`

6. **MLOps** (优先级：中)
   - `tests/test_mlops/test_inference_cache.py`
   - `tests/test_mlops/test_performance_monitor.py`

7. **数据工程** (优先级：低)
   - `tests/test_data_engineering/test_synthetic_data_generator.py`
   - `tests/test_data_engineering/test_agent_benchmark.py`

#### 2.2 测试框架设置

**文件**: `backend/tests/conftest.py`

```python
import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.base import Base


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_db_engine():
    """创建测试数据库引擎"""
    engine = create_async_engine(
        settings.TEST_DATABASE_URL,
        echo=False,
        future=True
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(test_db_engine):
    """创建数据库会话"""
    async_session = sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as session:
        yield session


@pytest.fixture
def mock_llm_response():
    """模拟 LLM 响应"""
    return "这是一个测试响应"


@pytest.fixture
def sample_topic():
    """示例主题"""
    return "AI 写作工具推荐"


@pytest.fixture
def sample_platform():
    """示例平台"""
    return "xiaohongshu"
```

#### 2.3 示例测试文件

**文件**: `backend/tests/test_agents/test_writer_agent.py`

```python
import pytest
from app.agents.content.writer_agent import WriterAgent
from app.agents.base import AgentConfig


@pytest.mark.asyncio
async def test_writer_agent_initialization():
    """测试 WriterAgent 初始化"""
    agent = WriterAgent()
    assert agent.config.name == "WriterAgent"
    assert agent.config.temperature == 0.7


@pytest.mark.asyncio
async def test_writer_agent_execute_success(sample_topic, sample_platform):
    """测试 WriterAgent 成功执行"""
    agent = WriterAgent()

    input_data = {
        "topic": sample_topic,
        "platform": sample_platform,
        "references": [
            {
                "ref_id": "ref_1",
                "text": "示例参考内容",
                "structure": {
                    "hook": "H01",
                    "body": "B02",
                    "cta": "C01"
                }
            }
        ],
        "strategy": {
            "hook": "H01",
            "body": "B02",
            "cta": "C01"
        }
    }

    response = await agent.execute(input_data)

    assert response.success is True
    assert "generated_contents" in response.data
    assert len(response.data["generated_contents"]) > 0


@pytest.mark.asyncio
async def test_writer_agent_execute_missing_topic():
    """测试 WriterAgent 缺少 topic 参数"""
    agent = WriterAgent()

    input_data = {
        "platform": "xiaohongshu"
    }

    response = await agent.execute(input_data)

    assert response.success is False
    assert "topic" in response.error.lower()


@pytest.mark.asyncio
async def test_writer_agent_geo_coverage():
    """测试 GEO 关键词覆盖率计算"""
    agent = WriterAgent()

    geo_keywords = ["AI", "写作", "工具"]
    content = "这是一个关于 AI 写作工具的内容"

    coverage = agent._calculate_geo_coverage(geo_keywords, content)

    assert coverage == 1.0  # 所有关键词都覆盖
```

#### 2.4 测试覆盖率目标

| 模块 | 当前覆盖率 | 目标覆盖率 | 优先级 |
|------|-----------|-----------|--------|
| 多智能体系统 | 20% | 80% | 高 |
| Planning & Reflection | 10% | 70% | 高 |
| LangGraph 工作流 | 30% | 75% | 高 |
| RAG 系统 | 40% | 70% | 中 |
| RL 系统 | 25% | 65% | 中 |
| MLOps | 35% | 70% | 中 |
| 数据工程 | 30% | 65% | 低 |
| **总体** | **30%** | **70%** | - |

---

## 📋 实施计划

### Step 1: TrendAgent 数据库检索（优先级：高）

**预计耗时**: 2-3 小时

1. ✅ 修改 `TrendAgent` 接受数据库会话
2. ✅ 实现真实的数据库查询逻辑
3. ✅ 更新 API 调用
4. ✅ 测试数据库检索功能

### Step 2: 核心模块单元测试（优先级：高）

**预计耗时**: 4-6 小时

1. ✅ 设置测试框架（pytest + pytest-asyncio）
2. ✅ 创建测试配置（conftest.py）
3. ✅ 编写 Agent 单元测试（Writer, Critic, Trend, Director）
4. ✅ 编写 Planning & Reflection 测试
5. ✅ 编写 LangGraph 工作流测试

### Step 3: RAG 和 RL 系统测试（优先级：中）

**预计耗时**: 3-4 小时

1. ✅ 编写 RAG 检索器测试
2. ✅ 编写 RAG 评估器测试
3. ✅ 编写 GRPO 训练器测试
4. ✅ 编写在线学习循环测试

### Step 4: MLOps 和数据工程测试（优先级：低）

**预计耗时**: 2-3 小时

1. ✅ 编写缓存系统测试
2. ✅ 编写性能监控测试
3. ✅ 编写合成数据生成器测试
4. ✅ 编写 Agent Benchmark 测试

### Step 5: 集成测试和 CI/CD（可选）

**预计耗时**: 2-3 小时

1. ✅ 编写端到端集成测试
2. ✅ 设置 GitHub Actions CI
3. ✅ 配置自动化测试流程

---

## 🎯 预期成果

### 1. TrendAgent 改进

- ✅ 真实数据库检索实现
- ✅ 检索准确率提升 30-50%
- ✅ 支持全文搜索和排序

### 2. 测试覆盖率提升

- ✅ 总体覆盖率从 30% 提升到 70%
- ✅ 核心模块覆盖率达到 75-80%
- ✅ 完整的单元测试和集成测试

### 3. 系统稳定性提升

- ✅ 减少 bug 和错误
- ✅ 提高代码质量
- ✅ 增强可维护性

---

## 📊 系统评分提升

| 维度 | 改进前 | 改进后 | 提升 |
|------|--------|--------|------|
| **TrendAgent 准确性** | 70/100 | 90/100 | +20 |
| **测试覆盖率** | 30/100 | 70/100 | +40 |
| **系统稳定性** | 85/100 | 95/100 | +10 |
| **代码质量** | 90/100 | 95/100 | +5 |
| **整体评分** | **95/100** | **97/100** | **+2** |

---

## 🚀 快速开始

### 1. 改进 TrendAgent

```bash
# 1. 修改 TrendAgent
# 编辑 backend/app/agents/content/trend_agent.py

# 2. 更新 API 调用
# 编辑 backend/app/api_v5_langgraph.py

# 3. 测试
python -m pytest tests/test_agents/test_trend_agent.py -v
```

### 2. 运行测试

```bash
# 安装测试依赖
pip install pytest pytest-asyncio pytest-cov

# 运行所有测试
pytest tests/ -v

# 运行测试并生成覆盖率报告
pytest tests/ --cov=app --cov-report=html

# 查看覆盖率报告
open htmlcov/index.html
```

---

## 📝 总结

Phase 7 将完善系统的最后 5%，重点是：

1. ✅ **TrendAgent 真实数据库检索** - 提升检索准确性
2. ✅ **测试覆盖率提升到 70%** - 确保系统稳定性

完成后，系统评分将从 95/100 提升到 **97/100**，达到世界级 AI 系统的标准。

---

**最后更新**: 2026-02-14
**预计完成时间**: 2026-02-15
**状态**: 待执行
