"""Adapters that connect the multimodal runtime to existing project services."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Protocol

from .multimodal_content_workflow import (
    ContentPlanner,
    ProductionState,
    StoryboardShot,
)


class StructuredOutputLLM(Protocol):
    async def structured_output(
        self,
        messages: List[Dict[str, str]],
        schema: Dict[str, Any],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """Return JSON-compatible structured output."""


class LLMContentPlanner(ContentPlanner):
    """Structured script and storyboard planner using the existing LLM layer."""

    SCRIPT_SCHEMA: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "hook": {"type": "string"},
            "body": {"type": "string"},
            "cta": {"type": "string"},
            "narration": {"type": "string"},
            "target_duration_seconds": {
                "type": "number",
                "minimum": 5,
                "maximum": 300,
            },
        },
        "required": [
            "title",
            "hook",
            "body",
            "cta",
            "narration",
            "target_duration_seconds",
        ],
    }

    STORYBOARD_SCHEMA: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "shots": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "shot_id": {"type": "string"},
                        "narration": {"type": "string"},
                        "visual_prompt": {"type": "string"},
                        "duration_seconds": {
                            "type": "number",
                            "minimum": 0.5,
                            "maximum": 60,
                        },
                        "camera": {"type": "string"},
                        "transition": {"type": "string"},
                    },
                    "required": [
                        "narration",
                        "visual_prompt",
                        "duration_seconds",
                    ],
                },
            }
        },
        "required": ["shots"],
    }

    def __init__(
        self,
        llm: StructuredOutputLLM,
        *,
        model: str | None = None,
        temperature: float = 0.4,
    ) -> None:
        self.llm = llm
        self.model = model
        self.temperature = temperature

    async def create_script(
        self,
        brief: Dict[str, Any],
        platform: str,
    ) -> Dict[str, Any]:
        prompt = {
            "platform": platform,
            "brief": brief,
            "requirements": [
                "Produce a concise short-form video script.",
                "Keep factual claims grounded in the supplied brief.",
                "Make the hook, body, CTA, and narration explicit.",
                "Return structured output only.",
            ],
        }
        result = await self.llm.structured_output(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a content-production planner. Convert a "
                        "campaign brief into a production-ready short-video script."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        prompt,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
            ],
            schema=self.SCRIPT_SCHEMA,
            model=self.model,
            temperature=self.temperature,
        )
        return dict(result)

    async def create_storyboard(
        self,
        script: Dict[str, Any],
        platform: str,
    ) -> List[StoryboardShot]:
        result = await self.llm.structured_output(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a storyboard planner. Split the supplied "
                        "short-video script into ordered, executable shots."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"platform": platform, "script": script},
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
            ],
            schema=self.STORYBOARD_SCHEMA,
            model=self.model,
            temperature=self.temperature,
        )

        raw_shots = result.get("shots", [])
        if not raw_shots:
            raise ValueError("LLM returned an empty storyboard")

        storyboard: List[StoryboardShot] = []
        for index, raw in enumerate(raw_shots, start=1):
            shot_id = str(raw.get("shot_id") or f"shot-{index}")
            duration = max(float(raw["duration_seconds"]), 0.5)
            metadata = {
                key: raw[key] for key in ("camera", "transition") if raw.get(key)
            }
            storyboard.append(
                StoryboardShot(
                    shot_id=shot_id,
                    narration=str(raw["narration"]),
                    visual_prompt=str(raw["visual_prompt"]),
                    duration_seconds=duration,
                    metadata=metadata,
                )
            )

        return storyboard


class ExistingPlatformPublisher:
    """Bridge the new production runtime to an existing platform adapter.

    The wrapped adapter must expose the project's existing
    `format_content(content)` and `publish(content, account_id)` methods.
    """

    def __init__(self, platform_adapter: Any, account_id: str) -> None:
        self.platform_adapter = platform_adapter
        self.account_id = account_id

    async def publish(self, state: ProductionState) -> Dict[str, Any]:
        if state.final_video is None:
            raise ValueError("final video is required before publish")

        payload = {
            "hook": state.script.get("hook", state.script.get("title", "")),
            "body": state.script.get("body", ""),
            "cta": state.script.get("cta", ""),
            "video_path": state.final_video.uri,
            "production_job_id": state.job_id,
        }

        formatted = await self.platform_adapter.format_content(payload)
        if not isinstance(formatted, dict):
            raise TypeError("platform adapter must return a dict")

        formatted["video_path"] = state.final_video.uri
        formatted["production_job_id"] = state.job_id

        result = await self.platform_adapter.publish(
            formatted,
            self.account_id,
        )
        if not isinstance(result, dict):
            raise TypeError("platform publish result must be a dict")
        return result
