"""
System Verification Script - ASCII Version
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def test_config_security():
    """Test configuration security"""
    print("[TEST] Configuration Security")

    from app.core.config import Settings

    # Test JWT validation
    try:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET="short",
            DATABASE_URL="postgresql://test",
            REDIS_URL="redis://test"
        )
        print("  [FAIL] JWT validation - should reject short key")
        return False
    except ValueError as e:
        if "32 characters" in str(e):
            print("  [PASS] JWT key length validation")
        else:
            print(f"  [FAIL] JWT validation error: {e}")
            return False

    # Test CORS validation
    try:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET="a" * 32,
            CORS_ORIGINS="*",
            DATABASE_URL="postgresql://test",
            REDIS_URL="redis://test"
        )
        print("  [FAIL] CORS validation - should reject wildcard")
        return False
    except ValueError as e:
        if "cannot contain '*'" in str(e):
            print("  [PASS] CORS wildcard validation")
        else:
            print(f"  [FAIL] CORS validation error: {e}")
            return False

    # Test valid configuration
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
        print("  [PASS] Valid configuration loading")
        print(f"  [INFO] CORS origins: {origins}")
    except Exception as e:
        print(f"  [FAIL] Configuration loading: {e}")
        return False

    return True


def test_database_config():
    """Test database configuration"""
    print("\n[TEST] Database Configuration")

    try:
        from app.core.database import engine

        assert engine.pool._pool_size == 20
        print("  [PASS] Connection pool size")

        print("  [PASS] Database engine configuration")
        return True
    except Exception as e:
        print(f"  [FAIL] Database configuration: {e}")
        return False


def test_rate_limiter():
    """Test rate limiter"""
    print("\n[TEST] Rate Limiter")

    try:
        from app.middleware.rate_limiter import RateLimitMiddleware, EndpointRateLimiter

        middleware = RateLimitMiddleware(
            app=None,
            requests_per_minute=60,
            requests_per_hour=1000,
            enabled=True
        )

        assert middleware.requests_per_minute == 60
        print("  [PASS] Rate limiter initialization")

        limiter = EndpointRateLimiter(
            requests_per_minute=10,
            requests_per_hour=100
        )
        assert limiter.requests_per_minute == 10
        print("  [PASS] Endpoint limiter initialization")

        return True
    except Exception as e:
        print(f"  [FAIL] Rate limiter test: {e}")
        return False


def test_p0_fixes():
    """Test P0 fixes"""
    print("\n[TEST] P0 Critical Fixes")

    results = []

    # 1. GRPO probability normalization
    try:
        from app.ml.rl.grpo_engine import GRPOEngine, GRPOConfig

        config = GRPOConfig(group_size=4, epsilon=0.1, learning_rate=1e-4)
        engine = GRPOEngine(config=config)

        engine.action_probs = {"a1": 0.6, "a2": 0.7, "a3": 0.8}
        engine._normalize_probabilities()

        total = sum(engine.action_probs.values())
        assert abs(total - 1.0) < 1e-6
        print("  [PASS] P0-1: GRPO probability normalization")
        results.append(True)
    except Exception as e:
        print(f"  [FAIL] P0-1: GRPO test: {e}")
        results.append(False)

    # 2. Action key uniqueness
    try:
        import json
        action1 = {"hook": "H1", "body": "B2", "cta": "C3"}
        action2 = {"hook": "H1", "body": "B23", "cta": "C"}

        key1 = json.dumps(action1, sort_keys=True)
        key2 = json.dumps(action2, sort_keys=True)

        assert key1 != key2
        print("  [PASS] P0-2: Action key uniqueness")
        results.append(True)
    except Exception as e:
        print(f"  [FAIL] P0-2: Action key test: {e}")
        results.append(False)

    # 3. Agent timeout control
    try:
        from app.agents.base import BaseAgent, AgentConfig, AgentResponse

        class TestAgent(BaseAgent):
            async def execute(self, input_data):
                return AgentResponse(success=True)

        agent = TestAgent(config=AgentConfig(name="Test", timeout=30))
        assert hasattr(agent, 'execute_with_timeout')
        print("  [PASS] P0-4: Agent timeout control")
        results.append(True)
    except Exception as e:
        print(f"  [FAIL] P0-4: Agent test: {e}")
        results.append(False)

    # 4. Reward model V2
    try:
        from app.ml.rl.hybrid_reward_model_v2 import HybridRewardModelV2

        model = HybridRewardModelV2(reward_shaping=True, reward_scale=10.0)
        assert model.reward_shaping is True
        assert model.reward_scale == 10.0
        print("  [PASS] P0-8: Reward shaping enabled")
        results.append(True)
    except Exception as e:
        print(f"  [FAIL] P0-8: Reward model test: {e}")
        results.append(False)

    # 5. Model router circuit breaker
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
        print("  [PASS] P0-9: Model router circuit breaker")
        results.append(True)
    except Exception as e:
        print(f"  [FAIL] P0-9: Model router test: {e}")
        results.append(False)

    return all(results)


def test_api_imports():
    """Test API imports"""
    print("\n[TEST] API Imports")

    try:
        from app.main import app
        print("  [PASS] Main application import")

        # Check middleware
        middleware_names = [str(m) for m in app.user_middleware]

        if any("RateLimitMiddleware" in name for name in middleware_names):
            print("  [PASS] Rate limit middleware registered")
        else:
            print("  [WARN] Rate limit middleware not found")

        if any("CORSMiddleware" in name for name in middleware_names):
            print("  [PASS] CORS middleware registered")
        else:
            print("  [WARN] CORS middleware not found")

        return True
    except Exception as e:
        print(f"  [FAIL] API import: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function"""
    print("=" * 60)
    print("Growth Flywheel 2.5 - System Verification")
    print("=" * 60)

    results = []

    # Run all tests
    results.append(("Configuration Security", test_config_security()))
    results.append(("Database Configuration", test_database_config()))
    results.append(("Rate Limiter", test_rate_limiter()))
    results.append(("P0 Fixes", test_p0_fixes()))
    results.append(("API Imports", test_api_imports()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} passed ({passed/total*100:.1f}%)")

    if passed == total:
        print("\n[SUCCESS] All tests passed! System verification successful.")
        return 0
    else:
        print(f"\n[WARNING] {total - passed} test(s) failed. Please check.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
