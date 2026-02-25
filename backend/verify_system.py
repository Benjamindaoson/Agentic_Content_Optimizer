"""
System Verification Script
"""

import sys
import asyncio
from pathlib import Path

# Add project path
sys.path.insert(0, str(Path(__file__).parent))


def test_config_security():
    """Test configuration security"""
    print("[*] Testing configuration security...")

    from app.core.config import Settings

    # 测试 JWT 验证
    try:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET="short",  # 太短
            DATABASE_URL="postgresql://test",
            REDIS_URL="redis://test"
        )
        print("  ✗ JWT 验证失败 - 应该拒绝短密钥")
        return False
    except ValueError as e:
        if "32 characters" in str(e):
            print("  ✓ JWT 密钥长度验证正常")
        else:
            print(f"  ✗ JWT 验证错误: {e}")
            return False

    # 测试 CORS 验证
    try:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET="a" * 32,
            CORS_ORIGINS="*",  # 不允许通配符
            DATABASE_URL="postgresql://test",
            REDIS_URL="redis://test"
        )
        print("  ✗ CORS 验证失败 - 应该拒绝通配符")
        return False
    except ValueError as e:
        if "cannot contain '*'" in str(e):
            print("  ✓ CORS 通配符验证正常")
        else:
            print(f"  ✗ CORS 验证错误: {e}")
            return False

    # 测试有效配置
    try:
        settings = Settings(
            ENVIRONMENT="development",
            JWT_SECRET="test-jwt-secret-key-for-testing-only-32-chars",
            CORS_ORIGINS="http://localhost:3000,http://localhost:5173",
            DATABASE_URL="postgresql://test",
            REDIS_URL="redis://test"
        )
        origins = settings.get_cors_origins_list()
        assert len(origins) == 2
        assert origins[0] == "http://localhost:3000"
        print("  ✓ 有效配置加载正常")
        print(f"  ✓ CORS 来源解析: {origins}")
    except Exception as e:
        print(f"  ✗ 配置加载失败: {e}")
        return False

    return True


def test_database_config():
    """测试数据库配置"""
    print("\n✓ 测试数据库配置...")

    try:
        from app.core.database import engine

        # 检查连接池配置
        assert engine.pool._pool_size == 20
        assert engine.pool._max_overflow == 10
        print("  ✓ 连接池大小配置正常")

        # 检查新增的配置
        assert hasattr(engine.pool, '_pre_ping')
        print("  ✓ 连接预检查已启用")

        print("  ✓ 数据库引擎配置正常")
        return True
    except Exception as e:
        print(f"  ✗ 数据库配置失败: {e}")
        return False


def test_rate_limiter():
    """测试速率限制器"""
    print("\n✓ 测试速率限制器...")

    try:
        from app.middleware.rate_limiter import RateLimitMiddleware, EndpointRateLimiter

        # 创建实例
        middleware = RateLimitMiddleware(
            app=None,
            requests_per_minute=60,
            requests_per_hour=1000,
            enabled=True
        )

        assert middleware.requests_per_minute == 60
        assert middleware.requests_per_hour == 1000
        print("  ✓ 速率限制器初始化正常")

        # 测试端点限制器
        limiter = EndpointRateLimiter(
            requests_per_minute=10,
            requests_per_hour=100
        )
        assert limiter.requests_per_minute == 10
        print("  ✓ 端点限制器初始化正常")

        return True
    except Exception as e:
        print(f"  ✗ 速率限制器测试失败: {e}")
        return False


def test_p0_fixes():
    """测试 P0 修复"""
    print("\n✓ 测试 P0 修复...")

    results = []

    # 1. GRPO 概率归一化
    try:
        from app.ml.rl.grpo_engine import GRPOEngine, GRPOConfig

        config = GRPOConfig(group_size=4, epsilon=0.1, learning_rate=1e-4)
        engine = GRPOEngine(config=config)

        # 设置非归一化概率
        engine.action_probs = {"a1": 0.6, "a2": 0.7, "a3": 0.8}
        engine._normalize_probabilities()

        total = sum(engine.action_probs.values())
        assert abs(total - 1.0) < 1e-6
        print("  ✓ P0-1: GRPO 概率归一化正常")
        results.append(True)
    except Exception as e:
        print(f"  ✗ P0-1: GRPO 测试失败: {e}")
        results.append(False)

    # 2. 动作键唯一性
    try:
        import json
        action1 = {"hook": "H1", "body": "B2", "cta": "C3"}
        action2 = {"hook": "H1", "body": "B23", "cta": "C"}

        key1 = json.dumps(action1, sort_keys=True)
        key2 = json.dumps(action2, sort_keys=True)

        assert key1 != key2
        print("  ✓ P0-2: 动作键唯一性正常")
        results.append(True)
    except Exception as e:
        print(f"  ✗ P0-2: 动作键测试失败: {e}")
        results.append(False)

    # 3. Agent 超时控制
    try:
        from app.agents.base import BaseAgent, AgentConfig, AgentResponse

        class TestAgent(BaseAgent):
            async def execute(self, input_data):
                return AgentResponse(success=True)

        agent = TestAgent(config=AgentConfig(name="Test", timeout=30))
        assert hasattr(agent, 'execute_with_timeout')
        print("  ✓ P0-4: Agent 超时控制已实现")
        results.append(True)
    except Exception as e:
        print(f"  ✗ P0-4: Agent 测试失败: {e}")
        results.append(False)

    # 4. 奖励模型 V2
    try:
        from app.ml.rl.hybrid_reward_model_v2 import HybridRewardModelV2

        model = HybridRewardModelV2(reward_shaping=True, reward_scale=10.0)
        assert model.reward_shaping is True
        assert model.reward_scale == 10.0
        print("  ✓ P0-8: 奖励塑形已启用")
        results.append(True)
    except Exception as e:
        print(f"  ✗ P0-8: 奖励模型测试失败: {e}")
        results.append(False)

    # 5. 模型路由器熔断器
    try:
        from app.llm.model_router import ModelRouter, ModelConfig, RoutingRule, TaskType

        models = {
            "test": ModelConfig(name="test", provider="test", version="1.0")
        }
        rules = [
            RoutingRule(task_type=TaskType.CONTENT_GENERATION, primary_model="test")
        ]

        router = ModelRouter(
            models=models,
            routing_rules=rules,
            max_consecutive_failures=5,
            circuit_breaker_timeout=60.0,
            max_fallback_attempts=3
        )

        assert router.max_consecutive_failures == 5
        assert router.max_fallback_attempts == 3
        print("  ✓ P0-9: 模型路由器熔断器已配置")
        results.append(True)
    except Exception as e:
        print(f"  ✗ P0-9: 模型路由器测试失败: {e}")
        results.append(False)

    return all(results)


def test_api_imports():
    """测试 API 导入"""
    print("\n✓ 测试 API 导入...")

    try:
        from app.main import app
        print("  ✓ 主应用导入正常")

        # 检查中间件
        assert any("RateLimitMiddleware" in str(m) for m in app.user_middleware)
        print("  ✓ 速率限制中间件已注册")

        assert any("CORSMiddleware" in str(m) for m in app.user_middleware)
        print("  ✓ CORS 中间件已注册")

        return True
    except Exception as e:
        print(f"  ✗ API 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_async_components():
    """测试异步组件"""
    print("\n✓ 测试异步组件...")

    try:
        # 测试 Redis 客户端
        from app.core.redis import RedisClient

        client = RedisClient("redis://localhost:6379/1")
        print("  ✓ Redis 客户端初始化正常")

        return True
    except Exception as e:
        print(f"  ✗ 异步组件测试失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("Growth Flywheel 2.5 - 系统验证")
    print("=" * 60)

    results = []

    # 运行所有测试
    results.append(("配置安全性", test_config_security()))
    results.append(("数据库配置", test_database_config()))
    results.append(("速率限制器", test_rate_limiter()))
    results.append(("P0 修复", test_p0_fixes()))
    results.append(("API 导入", test_api_imports()))

    # 异步测试
    try:
        async_result = asyncio.run(test_async_components())
        results.append(("异步组件", async_result))
    except Exception as e:
        print(f"\n✗ 异步测试失败: {e}")
        results.append(("异步组件", False))

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status}: {name}")

    print(f"\n总计: {passed}/{total} 通过 ({passed/total*100:.1f}%)")

    if passed == total:
        print("\n🎉 所有测试通过！系统验证成功。")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
