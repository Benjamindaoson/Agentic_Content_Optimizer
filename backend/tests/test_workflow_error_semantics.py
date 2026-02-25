from types import SimpleNamespace

import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_generate_preserves_http_exception(monkeypatch):
    from app.api.v1 import api_v5_langgraph as workflow_api

    async def _raise_rate_limit(_user):
        raise HTTPException(status_code=429, detail="rate limited")

    monkeypatch.setattr(workflow_api, "_check_rate_limit", _raise_rate_limit)

    req = workflow_api.WorkflowGenerateRequest(topic="test topic")
    fake_user = SimpleNamespace(id=1, role="user")

    with pytest.raises(HTTPException) as exc:
        await workflow_api.generate_content_with_workflow(req, current_user=fake_user)

    assert exc.value.status_code == 429
