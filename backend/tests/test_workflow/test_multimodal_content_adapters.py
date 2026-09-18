"""Tests for multimodal production adapters."""

import pytest

from app.engine.agents.workflow.multimodal_content_adapters import (
    ExistingPlatformPublisher,
    LLMContentPlanner,
)
from app.engine.agents.workflow.multimodal_content_workflow import (
    AssetKind,
    MediaAsset,
    ProductionState,
)


class FakeStructuredLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def structured_output(
        self,
        messages,
        schema,
        model=None,
        temperature=0.7,
    ):
        self.calls += 1
        if "shots" in schema.get("properties", {}):
            return {
                "shots": [
                    {
                        "shot_id": "intro",
                        "narration": "开场旁白",
                        "visual_prompt": "产品快速特写",
                        "duration_seconds": 2.5,
                        "camera": "close-up",
                    },
                    {
                        "narration": "核心卖点",
                        "visual_prompt": "用户使用场景",
                        "duration_seconds": 5,
                        "transition": "cut",
                    },
                ]
            }

        return {
            "title": "新品介绍",
            "hook": "3 秒看懂核心卖点",
            "body": "核心内容",
            "cta": "了解更多",
            "narration": "完整旁白",
            "target_duration_seconds": 15,
        }


class FakePlatformAdapter:
    def __init__(self) -> None:
        self.formatted = None
        self.published = None

    async def format_content(self, content):
        self.formatted = dict(content)
        return {
            "script": (
                f"{content['hook']}\n"
                f"{content['body']}\n"
                f"{content['cta']}"
            )
        }

    async def publish(self, content, account_id):
        self.published = dict(content)
        return {
            "status": "success",
            "post_id": "dy-001",
            "account_id": account_id,
        }


@pytest.mark.asyncio
async def test_llm_content_planner_builds_script_and_storyboard():
    llm = FakeStructuredLLM()
    planner = LLMContentPlanner(llm)

    script = await planner.create_script(
        {"product": "工业设备", "goal": "解释核心卖点"},
        "douyin",
    )
    storyboard = await planner.create_storyboard(script, "douyin")

    assert script["hook"] == "3 秒看懂核心卖点"
    assert len(storyboard) == 2
    assert storyboard[0].shot_id == "intro"
    assert storyboard[1].shot_id == "shot-2"
    assert storyboard[0].metadata["camera"] == "close-up"
    assert llm.calls == 2


@pytest.mark.asyncio
async def test_existing_platform_publisher_preserves_final_video():
    adapter = FakePlatformAdapter()
    publisher = ExistingPlatformPublisher(
        platform_adapter=adapter,
        account_id="account-1",
    )
    state = ProductionState(
        job_id="job-1",
        brief={"topic": "新品"},
        platform="douyin",
        script={
            "title": "新品介绍",
            "hook": "开场",
            "body": "正文",
            "cta": "行动",
        },
        final_video=MediaAsset(
            asset_id="final-1",
            kind=AssetKind.FINAL_VIDEO,
            uri="s3://bucket/final.mp4",
            provider="assembler",
        ),
    )

    result = await publisher.publish(state)

    assert result["post_id"] == "dy-001"
    assert adapter.published["video_path"] == "s3://bucket/final.mp4"
    assert adapter.published["production_job_id"] == "job-1"
