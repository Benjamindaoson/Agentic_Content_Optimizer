"""Authorization and idempotency guards for the multimodal task API."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import api_multimodal_production as api
from app.engine.agents.workflow.multimodal_content_workflow import ProductionState
from app.ml.training.schemas import Outcome
from app.models.user import UserRole


class FakeStore:
    def __init__(self, state):
        self.state = state
        self.saved = []

    async def load(self, job_id):
        return self.state

    async def save(self, state):
        self.saved.append(state)


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeDB:
    def __init__(self, outcome=None):
        self.outcome = outcome
        self.flushes = 0

    async def execute(self, statement):
        return FakeResult(self.outcome)

    async def flush(self):
        self.flushes += 1

    def add(self, value):
        self.outcome = value


def _user():
    return SimpleNamespace(id="user-1", role=UserRole.USER)


def _state(**metadata):
    return ProductionState(
        job_id="job-1",
        brief={"topic": "demo"},
        platform="tiktok",
        metadata={"owner_id": "user-1", **metadata},
    )


@pytest.mark.asyncio
async def test_submit_authorizes_trace_before_attaching(monkeypatch):
    checked = []

    async def assert_trace_access(db, trace_id, user):
        checked.append((db, trace_id, user.id))

    class Service:
        async def submit(self, **kwargs):
            assert kwargs["metadata"]["trace_id"] == "trace-1"
            return "job-1"

    monkeypatch.setattr(api, "_assert_trace_access", assert_trace_access)
    monkeypatch.setattr(api, "_get_service_or_503", lambda: Service())
    db = FakeDB()

    result = await api.submit_job(
        api.SubmitProductionJobRequest(
            brief={"topic": "demo"},
            trace_id="trace-1",
        ),
        current_user=_user(),
        db=db,
    )

    assert result["job_id"] == "job-1"
    assert checked == [(db, "trace-1", "user-1")]


@pytest.mark.asyncio
async def test_feedback_rejects_video_not_bound_to_job(monkeypatch):
    store = FakeStore(_state(tiktok_post_ids=["owned-video"]))
    monkeypatch.setattr(api, "get_multimodal_checkpoint_store", lambda: store)

    with pytest.raises(HTTPException) as exc_info:
        await api.ingest_tiktok_feedback(
            "job-1",
            api.TikTokFeedbackRequest(video_id="other-video"),
            current_user=_user(),
            db=FakeDB(),
        )

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_tiktok_publish_returns_existing_result_without_republishing(monkeypatch):
    previous = {"publish_id": "publish-1", "status": "submitted"}
    store = FakeStore(
        _state(tiktok_publish_id="publish-1", last_publish_result=previous)
    )
    monkeypatch.setattr(api, "get_multimodal_checkpoint_store", lambda: store)

    def should_not_create_publisher(*args, **kwargs):
        raise AssertionError("an already submitted job must not publish again")

    monkeypatch.setattr(api, "_get_tiktok_publisher", should_not_create_publisher)

    result = await api.publish_tiktok(
        "job-1", api.TikTokPublishRequest(), current_user=_user()
    )

    assert result == previous


@pytest.mark.asyncio
async def test_tiktok_publish_blocks_retry_after_ambiguous_attempt(monkeypatch):
    store = FakeStore(_state(tiktok_publish_attempted=True))
    monkeypatch.setattr(api, "get_multimodal_checkpoint_store", lambda: store)

    with pytest.raises(HTTPException) as exc_info:
        await api.publish_tiktok(
            "job-1", api.TikTokPublishRequest(), current_user=_user()
        )

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_repeated_identical_feedback_does_not_resync_rl(monkeypatch):
    state = _state(
        tiktok_post_ids=["video-1"],
        trace_id="trace-1",
    )
    store = FakeStore(state)
    monkeypatch.setattr(api, "get_multimodal_checkpoint_store", lambda: store)

    class Publisher:
        async def query_video_metrics(self, video_id):
            return {
                "view_count": 100,
                "like_count": 10,
                "comment_count": 2,
                "share_count": 3,
            }

    monkeypatch.setattr(api, "_get_tiktok_publisher", lambda: Publisher())

    async def should_not_sync(**kwargs):
        raise AssertionError("RL synchronization must be idempotent")

    monkeypatch.setattr(api, "sync_outcome_to_rl", should_not_sync)
    outcome = Outcome(
        id="outcome-1",
        trace_id="trace-1",
        impressions=100,
        likes=10,
        comments=2,
        shares=3,
        engagement_score=200.0,
        time_bucket="24h",
        rl_synced=1,
    )

    result = await api.ingest_tiktok_feedback(
        "job-1",
        api.TikTokFeedbackRequest(video_id="video-1", time_bucket="24h"),
        current_user=_user(),
        db=FakeDB(outcome),
    )

    assert result["rl_synced"] is True
    assert result["rl_sync_status"] == "already_synced"
