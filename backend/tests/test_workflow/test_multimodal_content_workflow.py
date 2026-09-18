"""Tests for the recoverable multimodal content-production workflow."""

import pytest

from app.engine.agents.workflow.multimodal_content_workflow import (
    AssetKind,
    InMemoryCheckpointStore,
    MediaAsset,
    MultimodalContentProductionAgent,
    ProductionStatus,
    QualityReport,
    StoryboardShot,
)


class FakePlanner:
    def __init__(self) -> None:
        self.script_calls = 0
        self.storyboard_calls = 0

    async def create_script(self, brief, platform):
        self.script_calls += 1
        return {
            "title": brief["topic"],
            "hook": "3 秒开场",
            "body": "核心内容",
            "cta": "立即行动",
            "platform": platform,
        }

    async def create_storyboard(self, script, platform):
        self.storyboard_calls += 1
        return [
            StoryboardShot(
                shot_id="shot-1",
                narration="开场",
                visual_prompt="产品特写",
                duration_seconds=3.0,
            ),
            StoryboardShot(
                shot_id="shot-2",
                narration="正文",
                visual_prompt="使用场景",
                duration_seconds=5.0,
            ),
        ]


class FakeMediaToolkit:
    def __init__(self, fail_visual_once: bool = False) -> None:
        self.visual_calls = 0
        self.voice_calls = 0
        self.assembly_calls = 0
        self.fail_visual_once = fail_visual_once

    async def generate_visual(self, shot, context):
        self.visual_calls += 1
        if self.fail_visual_once:
            self.fail_visual_once = False
            raise RuntimeError("temporary video provider timeout")
        return MediaAsset(
            asset_id=f"asset-{shot.shot_id}",
            kind=AssetKind.VIDEO,
            uri=f"memory://{shot.shot_id}.mp4",
            provider="fake-video",
        )

    async def synthesize_voice(self, script, context):
        self.voice_calls += 1
        return MediaAsset(
            asset_id="voice-1",
            kind=AssetKind.AUDIO,
            uri="memory://voice.wav",
            provider="fake-tts",
        )

    async def assemble_video(
        self,
        storyboard,
        visual_assets,
        voice_asset,
        context,
    ):
        self.assembly_calls += 1
        assert len(visual_assets) == len(storyboard)
        assert voice_asset.kind == AssetKind.AUDIO
        return MediaAsset(
            asset_id="final-1",
            kind=AssetKind.FINAL_VIDEO,
            uri="memory://final.mp4",
            provider="fake-assembler",
        )


class FakeEvaluator:
    def __init__(self, passed: bool = True) -> None:
        self.calls = 0
        self.passed = passed

    async def evaluate(self, state):
        self.calls += 1
        return QualityReport(
            score=0.91 if self.passed else 0.42,
            passed=self.passed,
            issues=[] if self.passed else ["audio_visual_mismatch"],
        )


class FakeApprovalGate:
    def __init__(self, approved: bool = True) -> None:
        self.calls = 0
        self.approved = approved

    async def approve(self, state):
        self.calls += 1
        return self.approved


class FakePublisher:
    def __init__(self) -> None:
        self.calls = 0

    async def publish(self, state):
        self.calls += 1
        return {
            "status": "published",
            "platform": state.platform,
            "post_id": "post-123",
        }


@pytest.mark.asyncio
async def test_full_multimodal_production_flow_completes():
    planner = FakePlanner()
    media = FakeMediaToolkit()
    evaluator = FakeEvaluator()
    approval = FakeApprovalGate()
    publisher = FakePublisher()
    store = InMemoryCheckpointStore()

    agent = MultimodalContentProductionAgent(
        planner=planner,
        media_toolkit=media,
        evaluator=evaluator,
        checkpoint_store=store,
        approval_gate=approval,
        publisher=publisher,
    )

    state = await agent.run(
        brief={"topic": "工业产品短视频"},
        platform="douyin",
    )

    assert state.status == ProductionStatus.COMPLETED
    assert state.final_video is not None
    assert state.quality_report is not None
    assert state.quality_report.passed is True
    assert state.approved is True
    assert state.publish_result["post_id"] == "post-123"
    assert media.visual_calls == 2
    assert publisher.calls == 1


@pytest.mark.asyncio
async def test_visual_generation_retries_transient_failure():
    media = FakeMediaToolkit(fail_visual_once=True)
    agent = MultimodalContentProductionAgent(
        planner=FakePlanner(),
        media_toolkit=media,
        evaluator=FakeEvaluator(),
        checkpoint_store=InMemoryCheckpointStore(),
        approval_gate=FakeApprovalGate(),
        max_retries=1,
        retry_backoff_seconds=0,
    )

    state = await agent.run(
        brief={"topic": "重试测试"},
        platform="douyin",
    )

    assert state.status == ProductionStatus.COMPLETED
    assert media.visual_calls == 3
    assert any(
        error["message"] == "temporary video provider timeout" for error in state.errors
    )


@pytest.mark.asyncio
async def test_resume_after_human_approval_does_not_replay_completed_work():
    planner = FakePlanner()
    media = FakeMediaToolkit()
    evaluator = FakeEvaluator()
    publisher = FakePublisher()
    store = InMemoryCheckpointStore()

    agent = MultimodalContentProductionAgent(
        planner=planner,
        media_toolkit=media,
        evaluator=evaluator,
        checkpoint_store=store,
        approval_gate=None,
        publisher=publisher,
        require_human_approval=True,
    )

    waiting = await agent.run(
        brief={"topic": "断点恢复测试"},
        platform="douyin",
        job_id="resume-job",
    )

    assert waiting.status == ProductionStatus.WAITING_APPROVAL
    assert publisher.calls == 0

    await agent.approve("resume-job")
    completed = await agent.run(job_id="resume-job")

    assert completed.status == ProductionStatus.COMPLETED
    assert planner.script_calls == 1
    assert planner.storyboard_calls == 1
    assert media.visual_calls == 2
    assert media.voice_calls == 1
    assert media.assembly_calls == 1
    assert evaluator.calls == 1
    assert publisher.calls == 1


@pytest.mark.asyncio
async def test_quality_gate_blocks_approval_and_publish():
    approval = FakeApprovalGate()
    publisher = FakePublisher()

    agent = MultimodalContentProductionAgent(
        planner=FakePlanner(),
        media_toolkit=FakeMediaToolkit(),
        evaluator=FakeEvaluator(passed=False),
        checkpoint_store=InMemoryCheckpointStore(),
        approval_gate=approval,
        publisher=publisher,
    )

    state = await agent.run(
        brief={"topic": "质量门测试"},
        platform="douyin",
    )

    assert state.status == ProductionStatus.NEEDS_REVISION
    assert state.quality_report is not None
    assert state.quality_report.passed is False
    assert approval.calls == 0
    assert publisher.calls == 0
