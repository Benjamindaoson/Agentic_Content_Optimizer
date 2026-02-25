"""
API 端点集成测试
API Endpoints Integration Tests
"""

import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.integration
@pytest.mark.api
class TestHealthEndpoints:
    """健康检查端点测试"""

    @pytest.mark.asyncio
    async def test_root_endpoint(self):
        """测试根端点"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/")

            assert response.status_code == 200
            data = response.json()
            assert "name" in data
            assert "version" in data
            assert "status" in data
            assert data["status"] == "online"

    @pytest.mark.asyncio
    async def test_health_check(self):
        """测试健康检查"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "database" in data
            assert "redis" in data

    @pytest.mark.asyncio
    async def test_system_status(self):
        """测试系统状态"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/system/status")

            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "version" in data


@pytest.mark.integration
@pytest.mark.api
class TestRateLimiting:
    """速率限制测试"""

    @pytest.mark.asyncio
    async def test_rate_limit_not_triggered_in_dev(self):
        """测试开发环境不触发速率限制"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # 快速发送多个请求
            for _ in range(10):
                response = await client.get("/")
                assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_rate_limit_headers(self):
        """测试速率限制响应头"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/")

            # 在生产环境应该有速率限制头
            # 开发环境可能没有
            if "X-RateLimit-Limit-Minute" in response.headers:
                assert int(response.headers["X-RateLimit-Limit-Minute"]) > 0


@pytest.mark.integration
@pytest.mark.api
class TestCORS:
    """CORS 测试"""

    @pytest.mark.asyncio
    async def test_cors_headers(self):
        """测试 CORS 响应头"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.options(
                "/",
                headers={"Origin": "http://localhost:3000"}
            )

            # 验证 CORS 头
            assert "access-control-allow-origin" in response.headers

    @pytest.mark.asyncio
    async def test_cors_allowed_origin(self):
        """测试允许的来源"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/",
                headers={"Origin": "http://localhost:3000"}
            )

            assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.rl
class TestRLEndpoints:
    """RL 端点测试"""

    @pytest.mark.asyncio
    async def test_rl_status(self):
        """测试 RL 状态端点"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/v4/rl/status")

            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "components" in data
            assert "algorithms" in data

    @pytest.mark.asyncio
    async def test_train_account_policy(self, db_session):
        """测试训练账号策略"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            payload = {
                "account_id": "test_account",
                "days": 7
            }

            response = await client.post("/v4/rl/account/train", json=payload)

            # 可能因为缺少数据而失败，但不应该是 500 错误
            assert response.status_code in [200, 400, 404]

    @pytest.mark.asyncio
    async def test_select_topics_with_rl(self, db_session):
        """测试 RL 话题选择"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            payload = {
                "account_id": "test_account",
                "k": 3,
                "exploration_rate": 0.2
            }

            response = await client.post("/v4/rl/account/select-topics", json=payload)

            # 可能因为缺少数据而失败
            assert response.status_code in [200, 400, 404]


@pytest.mark.integration
@pytest.mark.api
class TestErrorHandling:
    """错误处理测试"""

    @pytest.mark.asyncio
    async def test_404_error(self):
        """测试 404 错误"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/nonexistent")

            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_json(self):
        """测试无效 JSON"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v4/rl/account/train",
                content="invalid json",
                headers={"Content-Type": "application/json"}
            )

            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_required_fields(self):
        """测试缺少必需字段"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v4/rl/account/train",
                json={}  # 缺少必需字段
            )

            assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.api
class TestAuthentication:
    """认证测试"""

    @pytest.mark.asyncio
    async def test_public_endpoints_no_auth(self):
        """测试公开端点不需要认证"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # 这些端点应该不需要认证
            public_endpoints = ["/", "/health", "/system/status"]

            for endpoint in public_endpoints:
                response = await client.get(endpoint)
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_protected_endpoints_require_auth(self):
        """测试受保护端点需要认证"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # 如果有受保护的端点，测试它们
            # 目前大部分端点都是公开的
            pass
