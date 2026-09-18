"""Tests for multimodal production providers, persistence, and eval."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.engine.agents.workflow.multimodal_artifacts import MinIOArtifactStore
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
    OpenAIMultimodalJudge,
)
from app.engine.agents.workflow.multimodal_media import (
    BrandTemplate,
    ElevenLabsTTSGenerator,
    FFmpegVideoAssembler,
    RunwayVideoGenerator,
)
from app.engine.agents.workflow.multimodal_persistence import (
    SQLAlchemyCheckpointStore,
    deserialize_production_state,
    serialize_production_state,
)
from app.models.multimodal_production import MultimodalProductionJob


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
async def test_sqlalchemy_checkpoint_store_persists_and_updates():
    database_url = os.environ["DATABASE_URL"].replace(
        "postgresql://",
        "postgresql+asyncpg://",
    )
    engine = create_async_engine(database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    store = SQLAlchemyCheckpointStore(session_factory=session_factory)

    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: MultimodalProductionJob.__table__.create(
                bind=sync_connection,
                checkfirst=True,
            )
        )

    try:
        state = ProductionState(
            job_id="db-job-1",
            brief={"topic": "数据库恢复"},
            platform="douyin",
            metadata={"owner_id": "7"},
        )

        await store.save(state)
        restored = await store.load("db-job-1")

        assert restored is not None
        assert restored.brief["topic"] == "数据库恢复"
        assert restored.metadata["owner_id"] == "7"
        assert restored.status == ProductionStatus.PENDING

        restored.status = ProductionStatus.WAITING_APPROVAL
        restored.stage = ProductionStage.APPROVAL
        restored.approved = False
        await store.save(restored)

        updated = await store.load("db-job-1")
        assert updated is not None
        assert updated.status == ProductionStatus.WAITING_APPROVAL
        assert updated.stage == ProductionStage.APPROVAL
    finally:
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: MultimodalProductionJob.__table__.drop(
                    bind=sync_connection,
                    checkfirst=True,
                )
            )
        await engine.dispose()


class FakeMinIOClient:
    def __init__(self):
        self.objects = {}
        self.buckets = set()

    def bucket_exists(self, bucket):
        return bucket in self.buckets

    def make_bucket(self, bucket):
        self.buckets.add(bucket)

    def fput_object(self, bucket, object_name, file_path):
        self.objects[(bucket, object_name)] = Path(file_path).read_bytes()

    def fget_object(self, bucket, object_name, file_path):
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        Path(file_path).write_bytes(self.objects[(bucket, object_name)])


@pytest.mark.asyncio
async def test_minio_artifact_store_persists_and_rematerializes(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"durable-video")
    client = FakeMinIOClient()
    store = MinIOArtifactStore(
        endpoint="minio:9000",
        access_key="test",
        secret_key="test",
        bucket="videos",
        cache_dir=str(tmp_path / "cache"),
        client=client,
    )

    persisted = await store.persist(
        MediaAsset(
            asset_id="asset-1",
            kind=AssetKind.VIDEO,
            uri=str(source),
            provider="test",
        ),
        job_id="job-1",
        category="visuals",
    )

    assert persisted.metadata["durable_uri"].startswith("s3://videos/job-1/visuals/")
    source.unlink()

    restored = await store.materialize(persisted)
    assert Path(restored.uri).read_bytes() == b"durable-video"
    assert restored.metadata["materialized_from"].startswith("s3://videos/")


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

        if (
            request.method == "GET"
            and str(request.url) == "https://cdn.example/video.mp4"
        ):
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
    def __init__(self, output_dir: str, **kwargs):
        super().__init__(output_dir=output_dir, ffmpeg_bin="true", **kwargs)
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


@pytest.mark.asyncio
async def test_ffmpeg_assembler_renders_subtitles_and_brand_template(tmp_path):
    visual = tmp_path / "input.mp4"
    voice = tmp_path / "voice.mp3"
    visual.write_bytes(b"video")
    voice.write_bytes(b"audio")

    assembler = RecordingAssembler(
        str(tmp_path / "artifacts"),
        brand_template=BrandTemplate(text="ACME"),
    )
    asset = await assembler.assemble(
        storyboard=[
            StoryboardShot(
                shot_id="s1",
                narration="第一句字幕",
                visual_prompt="视觉",
                duration_seconds=3,
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
        context={"job_id": "brand-job", "platform": "douyin"},
    )

    final_command = " ".join(assembler.commands[-1])
    assert "subtitles=" in final_command
    assert "drawtext=" in final_command
    assert asset.metadata["subtitles_rendered"] is True
    assert asset.metadata["brand_template_applied"] is True


@pytest.mark.asyncio
async def test_ffmpeg_assembler_suppresses_brand_for_tiktok(tmp_path):
    visual = tmp_path / "input.mp4"
    voice = tmp_path / "voice.mp3"
    visual.write_bytes(b"video")
    voice.write_bytes(b"audio")

    assembler = RecordingAssembler(
        str(tmp_path / "artifacts"),
        brand_template=BrandTemplate(text="ACME"),
    )
    asset = await assembler.assemble(
        storyboard=[
            StoryboardShot(
                shot_id="s1",
                narration="字幕",
                visual_prompt="视觉",
                duration_seconds=3,
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
        context={"job_id": "tiktok-brand-job", "platform": "tiktok"},
    )

    final_command = " ".join(assembler.commands[-1])
    assert "subtitles=" in final_command
    assert "drawtext=" not in final_command
    assert asset.metadata["brand_template_applied"] is False
    assert asset.metadata["brand_template_suppressed_for_tiktok"] is True


class FakeResponsesAPI:
    def __init__(self):
        self.last_request = None

    async def create(self, **kwargs):
        self.last_request = kwargs
        return SimpleNamespace(
            output_text=(
                '{"score": 0.92, "issues": [], '
                '"dimensions": {"visual_story_alignment": 0.95, '
                '"visual_quality": 0.9, "publish_readiness": 0.91}, '
                '"reasoning": "frames align with the storyboard"}'
            )
        )


class FakeOpenAIClient:
    def __init__(self):
        self.responses = FakeResponsesAPI()


class StubFrameJudge(OpenAIMultimodalJudge):
    async def _sample_frames(self, video_path, output_dir, state):
        paths = []
        for index in range(2):
            frame = output_dir / f"frame_{index}.jpg"
            frame.write_bytes(b"jpeg-bytes")
            paths.append(frame)
        return paths


@pytest.mark.asyncio
async def test_openai_multimodal_judge_sends_sampled_frames(tmp_path):
    video = tmp_path / "final.mp4"
    video.write_bytes(b"video")
    client = FakeOpenAIClient()
    judge = StubFrameJudge(
        api_key="test-key",
        model="gpt-6-astra",
        client=client,
        sample_count=2,
    )
    state = ProductionState(
        job_id="judge-job",
        brief={"topic": "产品"},
        platform="douyin",
        script={"title": "标题", "hook": "钩子", "body": "正文", "cta": "行动"},
        storyboard=[
            StoryboardShot(
                shot_id="s1",
                narration="旁白",
                visual_prompt="产品镜头",
                duration_seconds=4,
            )
        ],
        final_video=MediaAsset(
            asset_id="final",
            kind=AssetKind.FINAL_VIDEO,
            uri=str(video),
            provider="ffmpeg",
        ),
    )

    result = await judge.evaluate(state)

    assert result["score"] == 0.92
    assert result["sampled_frames"] == 2
    request_content = client.responses.last_request["input"][0]["content"]
    image_inputs = [item for item in request_content if item["type"] == "input_image"]
    assert len(image_inputs) == 2
    assert image_inputs[0]["image_url"].startswith("data:image/jpeg;base64,")


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
