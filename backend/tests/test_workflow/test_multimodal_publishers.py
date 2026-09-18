"""Tests for real platform publishers used by multimodal production."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.engine.agents.workflow.multimodal_content_workflow import (
    AssetKind,
    MediaAsset,
    ProductionState,
    QualityReport,
    StoryboardShot,
)
from app.engine.agents.workflow.multimodal_publishers import (
    TikTokContentPublisher,
)


def _approved_tiktok_state(video_path: Path) -> ProductionState:
    return ProductionState(
        job_id="publish-job",
        brief={"topic": "产品演示"},
        platform="tiktok",
        script={
            "title": "产品演示",
            "hook": "三秒看懂",
            "body": "正文",
            "cta": "了解更多",
        },
        storyboard=[
            StoryboardShot(
                shot_id="s1",
                narration="旁白",
                visual_prompt="产品特写",
                duration_seconds=5,
            )
        ],
        final_video=MediaAsset(
            asset_id="final",
            kind=AssetKind.FINAL_VIDEO,
            uri=str(video_path),
            provider="ffmpeg",
        ),
        quality_report=QualityReport(score=0.95, passed=True),
        approved=True,
    )


@pytest.mark.asyncio
async def test_tiktok_direct_post_uploads_video_and_honors_creator_settings(tmp_path):
    video = tmp_path / "final.mp4"
    video.write_bytes(b"video-bytes")
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "POST"
            and request.url.path == "/v2/post/publish/creator_info/query/"
        ):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "privacy_level_options": ["SELF_ONLY"],
                        "comment_disabled": True,
                        "duet_disabled": False,
                        "stitch_disabled": True,
                        "max_video_post_duration_sec": 60,
                    },
                    "error": {"code": "ok", "message": ""},
                },
            )

        if (
            request.method == "POST"
            and request.url.path == "/v2/post/publish/video/init/"
        ):
            captured["init"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "data": {
                        "publish_id": "pub-123",
                        "upload_url": "https://upload.example/video",
                    },
                    "error": {"code": "ok", "message": ""},
                },
            )

        if request.method == "PUT" and str(request.url) == "https://upload.example/video":
            captured["upload"] = bytes(request.content)
            captured["content_range"] = request.headers["Content-Range"]
            return httpx.Response(201)

        if (
            request.method == "POST"
            and request.url.path == "/v2/post/publish/status/fetch/"
        ):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "status": "PROCESSING_UPLOAD",
                        "uploaded_bytes": len(video.read_bytes()),
                    },
                    "error": {"code": "ok", "message": ""},
                },
            )

        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    publisher = TikTokContentPublisher(
        access_token="token",
        privacy_level="SELF_ONLY",
        client=client,
    )

    state = _approved_tiktok_state(video)
    result = await publisher.publish(
        state,
        caption="用户确认后的标题 #demo",
        brand_content_toggle=True,
        brand_organic_toggle=False,
    )
    await client.aclose()

    assert result["publish_id"] == "pub-123"
    assert result["status"] == "PROCESSING_UPLOAD"
    assert captured["upload"] == b"video-bytes"
    assert captured["content_range"] == "bytes 0-10/11"

    post_info = captured["init"]["post_info"]
    assert post_info["title"] == "用户确认后的标题 #demo"
    assert post_info["privacy_level"] == "SELF_ONLY"
    assert post_info["disable_comment"] is True
    assert post_info["disable_duet"] is False
    assert post_info["disable_stitch"] is True
    assert post_info["brand_content_toggle"] is True
    assert post_info["brand_organic_toggle"] is False
    assert post_info["is_aigc"] is True


@pytest.mark.asyncio
async def test_tiktok_direct_post_rejects_unapproved_job(tmp_path):
    video = tmp_path / "final.mp4"
    video.write_bytes(b"video")
    state = _approved_tiktok_state(video)
    state.approved = False

    publisher = TikTokContentPublisher(access_token="token")
    with pytest.raises(ValueError, match="human approval"):
        await publisher.publish(state)


@pytest.mark.asyncio
async def test_tiktok_video_metrics_query_returns_engagement_fields():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v2/video/query/"
        assert "view_count" in request.url.query.decode()
        assert json.loads(request.content) == {
            "filters": {"video_ids": ["video-1"]}
        }
        return httpx.Response(
            200,
            json={
                "data": {
                    "videos": [
                        {
                            "id": "video-1",
                            "like_count": 10,
                            "comment_count": 2,
                            "share_count": 3,
                            "view_count": 100,
                            "is_aigc": True,
                        }
                    ]
                },
                "error": {"code": "ok", "message": ""},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    publisher = TikTokContentPublisher(
        access_token="token",
        client=client,
    )

    metrics = await publisher.query_video_metrics("video-1")
    await client.aclose()

    assert metrics["view_count"] == 100
    assert metrics["like_count"] == 10
    assert metrics["comment_count"] == 2
    assert metrics["share_count"] == 3
    assert metrics["is_aigc"] is True
