"""Tests for multimodal production providers, persistence, and eval."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from app.engine.agents.workflow.multimodal_content_workflow import (
    AssetKind,
    MediaAsset,
    ProductionStage,
    ProductionState,
    ProductionStatus,
    QualityReport,
    StoryboardShot,
)
from app.engine.agents.workflow.multimodal_eval import (
    MultimodalEvaluationHarness,
)
from app.engine.agents.workflow.multimodal_media import (
    ElevenLabsTTSGenerator,
    FFmpegVideoAssembler,
    RunwayVideoGenerator,
)
from app.engine.agents.workflow.multimodal_persistence import (
    deserialize_production_state,
    serialize_production_state,
)


def test_production_state_round_trip_serialization():
    state = ProductionState(
        job_id="job-1",
        brief={"topic": "产品介绍"},
        platform="douyin",
        status=ProductionStatus.WAITING_APPROVAL,
        stage=ProductionStage.APPROVAL,
        script={"title": "标题", "hook": "开场", "body": "正文", "cta": "行动"},
        storyboard=[
            StoryboardShot(
                shot_id="s1",
                narration="旁白",
                visual_prompt="产品特写",
                duration_seconds=5,
            )
        ],
        visual_assets={
            "s1": MediaAsset(
                asset_id="v1",
                kind=AssetKind.VIDEO,
                uri="/tmp/s1.mp4",
                provider="runway",
            )
        },
        voice_asset=MediaAsset(
            asset_id="a1",
            kind=AssetKind.AUDIO,
            uri="/tmp/voice.mp3",
            provider="elevenlabs",
        ),
        final_video=MediaAsset(
            asset_id="f1",
            kind=AssetKind.FINAL_VIDEO,
            uri="/tmp/final.mp4",
            provider="ffmpeg",
        ),
        quality_report=QualityReport(score=0.95, passed=True),
        metadata={"owner_id": "42"},
    )

    restored = deserialize_production_state(serialize_production_state(state))

    assert restored.job_id == state.job_id
    assert restored.status == ProductionStatus.WAITING_APPROVAL
    assert restored.stage == ProductionStage.APPROVAL
    assert restored.visual_assets["s1"].kind == AssetKind.VIDEO
    assert restored.voice_asset.provider == "elevenlabs"
    assert restored.final_video.kind == AssetKind.FINAL_VIDEO
    assert restored.quality_report.passed is True
    assert restored.metadata["owner_id"] == "42"


@pytest.mark.asyncio
async def test_runway_video_generator_polls_and_downloads(tmp_path):
    calls = {"task": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/image_to_video":
            payload = __import__("json").loads(request.content)
            assert payload["model"] == "gen4.5"
            assert payload["ratio"] == "720:1280"
            assert payload["promptText"] == "产品旋转特写"
            return httpx.Response(200, json={"id": "task-123"})

        if request.method == "GET" and request.url.path == "/v1/tasks/task-123":
            calls["task"] += 1
            return httpx.Response(
                200,
                json={
                    "id": "task-123",
                    "status": "SUCCEEDED",
                    "output": ["https://cdn.example/video.mp4"],
                },
            )

        if request.method == "GET" and str(request.url) == "https://cdn.example/video.mp4":
            return httpx.Response(200, content=b"fake-video-bytes")

        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    generator = RunwayVideoGenerator(
        api_secret="test-secret",
        output_dir=str(tmp_path),
        client=client,
        poll_interval_seconds=0,
    )

    asset = await generator.generate(
        StoryboardShot(
            shot_id="shot-1",
            narration="旁白",
            visual_prompt="产品旋转特写",
            duration_seconds=3,
        ),
        {"job_id": "job-1"},
    )
    await client.aclose()

    assert calls["task"] == 1
    assert asset.provider == "runway"
    assert asset.kind == AssetKind.VIDEO
    assert Path(asset.uri).read_bytes() == b"fake-video-bytes"
    assert asset.metadata["task_id"] == "task-123"


@pytest.mark.asyncio
async def test_elevenlabs_tts_downloads_audio(tmp_path):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/text-to-speech/voice-1"
        assert request.headers["xi-api-key"] == "tts-key"
        return httpx.Response(
            200,
            content=b"fake-mp3",
            headers={
                "request-id": "req-1",
                "x-trace-id": "trace-1",
                "character-cost": "12",
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    tts = ElevenLabsTTSGenerator(
        api_key="tts-key",
        voice_id="voice-1",
        output_dir=str(tmp_path),
        client=client,
    )

    asset = await tts.synthesize(
        {"narration": "这是旁白"},
        {"job_id": "job-tts"},
    )
    await client.aclose()

    assert asset.kind == AssetKind.AUDIO
    assert Path(asset.uri).read_bytes() == b"fake-mp3"
    assert asset.metadata["request_id"] == "req-1"


class RecordingAssembler(FFmpegVideoAssembler):
    def __init__(self, output_dir: str):
        super().__init__(output_dir=output_dir, ffmpeg_bin="true")
        self.commands = []

    async def _run(self, *args: str) -> None:
        self.commands.append(args)
        output = Path(args[-1])
        if output.suffix == ".mp4":
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"video")


@pytest.mark.asyncio
async def test_ffmpeg_assembler_builds_vertical_short_video_pipeline(tmp_path):
    visual = tmp_path / "input.mp4"
    voice = tmp_path / "voice.mp3"
    visual.write_bytes(b"source-video")
    voice.write_bytes(b"source-audio")

    assembler = RecordingAssembler(str(tmp_path / "artifacts"))
    asset = await assembler.assemble(
        storyboard=[
            StoryboardShot(
                shot_id="s1",
                narration="旁白",
                visual_prompt="视觉",
                duration_seconds=4,
            )
        ],
        visual_assets={
            "s1": MediaAsset(
                asset_id="v1",
                kind=AssetKind.VIDEO,
                uri=str(visual),
                provider="runway",
            )
        },
        voice_asset=MediaAsset(
            asset_id="a1",
            kind=AssetKind.AUDIO,
            uri=str(voice),
            provider="elevenlabs",
        ),
        context={"job_id": "assembly-job"},
    )

    assert asset.kind == AssetKind.FINAL_VIDEO
    assert asset.provider == "ffmpeg"
    assert len(assembler.commands) == 3
    normalize_command = " ".join(assembler.commands[0])
    assert "scale=720:1280" in normalize_command
    assert Path(asset.uri).exists()


class ProbeHarness(MultimodalEvaluationHarness):
    async def _probe(self, path: Path):
        return {
            "streams": [
                {"codec_type": "video"},
                {"codec_type": "audio"},
            ],
            "format": {"duration": "5.0"},
        }


@pytest.mark.asyncio
async def test_multimodal_eval_requires_complete_artifacts(tmp_path):
    final_video = tmp_path / "final.mp4"
    final_video.write_bytes(b"video")

    state = ProductionState(
        job_id="eval-job",
        brief={"topic": "产品"},
        platform="douyin",
        script={
            "title": "标题",
            "hook": "开场",
            "body": "正文",
            "cta": "行动",
        },
        storyboard=[
            StoryboardShot(
                shot_id="s1",
                narration="旁白",
                visual_prompt="视觉",
                duration_seconds=5,
            )
        ],
        visual_assets={
            "s1": MediaAsset(
                asset_id="v1",
                kind=AssetKind.VIDEO,
                uri=str(tmp_path / "shot.mp4"),
                provider="runway",
            )
        },
        final_video=MediaAsset(
            asset_id="final",
            kind=AssetKind.FINAL_VIDEO,
            uri=str(final_video),
            provider="ffmpeg",
        ),
    )

    report = await ProbeHarness().evaluate(state)

    assert report.passed is True
    assert report.score == 1.0
    assert report.issues == []
