import pytest


@pytest.mark.asyncio
async def test_readiness_ready(monkeypatch):
    import app.main as main_mod

    main_mod.app.state.startup_state = {
        "started": True,
        "core_ready": True,
        "optional_inits": {"mlops": True},
        "routers_loaded": ["app.api.v1.api_v5_langgraph"],
        "routers_skipped": [],
        "started_at": 123,
    }

    async def _db_ready(timeout_sec: int = 2):
        return True

    async def _redis_ready():
        return True

    monkeypatch.setattr(main_mod, "check_db_ready", _db_ready)
    monkeypatch.setattr(main_mod.redis_client, "ping", _redis_ready)

    payload, status = await main_mod._build_readiness_payload()
    assert status == 200
    assert payload["status"] == "ready"
    assert payload["degraded"] is False


@pytest.mark.asyncio
async def test_readiness_not_ready_when_dependency_down(monkeypatch):
    import app.main as main_mod

    main_mod.app.state.startup_state = {
        "started": True,
        "core_ready": True,
        "optional_inits": {"mlops": False},
        "routers_loaded": ["app.api.v1.api_v5_langgraph"],
        "routers_skipped": ["app.api.v1.api_data_import"],
        "started_at": 123,
    }

    async def _db_not_ready(timeout_sec: int = 2):
        return False

    async def _redis_ready():
        return True

    monkeypatch.setattr(main_mod, "check_db_ready", _db_not_ready)
    monkeypatch.setattr(main_mod.redis_client, "ping", _redis_ready)

    payload, status = await main_mod._build_readiness_payload()
    assert status == 503
    assert payload["status"] == "not_ready"
    assert payload["degraded"] is True
