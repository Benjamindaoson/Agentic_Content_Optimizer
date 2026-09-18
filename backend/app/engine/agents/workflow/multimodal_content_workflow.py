"""Durable multimodal content-production agent runtime.

This module turns the existing content-generation stack into a recoverable,
long-running production workflow. It deliberately keeps model/media providers
behind small protocols so cloud APIs, local models, MCP tools, or test doubles
can be plugged in without coupling orchestration to a vendor.
"""

from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol
from uuid import uuid4


class ProductionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    NEEDS_REVISION = "needs_revision"
    COMPLETED = "completed"
    FAILED = "failed"


class ProductionStage(str, Enum):
    PLAN_SCRIPT = "plan_script"
    BUILD_STORYBOARD = "build_storyboard"
    GENERATE_VISUALS = "generate_visuals"
    SYNTHESIZE_VOICE = "synthesize_voice"
    ASSEMBLE_VIDEO = "assemble_video"
    QUALITY_GATE = "quality_gate"
    APPROVAL = "approval"
    PUBLISH = "publish"
    COMPLETED = "completed"


class AssetKind(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    FINAL_VIDEO = "final_video"


@dataclass
class StoryboardShot:
    shot_id: str
    narration: str
    visual_prompt: str
    duration_seconds: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MediaAsset:
    asset_id: str
    kind: AssetKind
    uri: str
    provider: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityReport:
    score: float
    passed: bool
    issues: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProductionState:
    job_id: str
    brief: Dict[str, Any]
    platform: str
    status: ProductionStatus = ProductionStatus.PENDING
    stage: ProductionStage = ProductionStage.PLAN_SCRIPT
    script: Dict[str, Any] = field(default_factory=dict)
    storyboard: List[StoryboardShot] = field(default_factory=list)
    visual_assets: Dict[str, MediaAsset] = field(default_factory=dict)
    voice_asset: Optional[MediaAsset] = None
    final_video: Optional[MediaAsset] = None
    quality_report: Optional[QualityReport] = None
    approved: bool = False
    publish_result: Optional[Dict[str, Any]] = None
    attempts: Dict[str, int] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ContentPlanner(Protocol):
    async def create_script(
        self, brief: Dict[str, Any], platform: str
    ) -> Dict[str, Any]:
        """Create a production-ready script from the campaign/content brief."""

    async def create_storyboard(
        self, script: Dict[str, Any], platform: str
    ) -> List[StoryboardShot]:
        """Turn a script into ordered shots with narration and visual prompts."""


class MediaToolkit(Protocol):
    async def generate_visual(
        self,
        shot: StoryboardShot,
        context: Dict[str, Any],
    ) -> MediaAsset:
        """Generate or retrieve the visual asset for one storyboard shot."""

    async def synthesize_voice(
        self,
        script: Dict[str, Any],
        context: Dict[str, Any],
    ) -> MediaAsset:
        """Generate the narration/voice track."""

    async def assemble_video(
        self,
        storyboard: List[StoryboardShot],
        visual_assets: Dict[str, MediaAsset],
        voice_asset: MediaAsset,
        context: Dict[str, Any],
    ) -> MediaAsset:
        """Assemble the final video from visual and audio assets."""


class QualityEvaluator(Protocol):
    async def evaluate(self, state: ProductionState) -> QualityReport:
        """Evaluate multimodal consistency, quality, policy, and platform fit."""


class ApprovalGate(Protocol):
    async def approve(self, state: ProductionState) -> bool:
        """Return True only when the content is approved for release."""


class Publisher(Protocol):
    async def publish(self, state: ProductionState) -> Dict[str, Any]:
        """Publish approved content and return platform identifiers/URLs."""


class CheckpointStore(Protocol):
    async def load(self, job_id: str) -> Optional[ProductionState]:
        """Load the latest checkpoint for a production job."""

    async def save(self, state: ProductionState) -> None:
        """Persist the latest durable state for a production job."""


class InMemoryCheckpointStore:
    """Small checkpoint store for tests and local development.

    Production deployments should provide a database/object-store backed
    implementation. The workflow only depends on the CheckpointStore protocol.
    """

    def __init__(self) -> None:
        self._states: Dict[str, ProductionState] = {}
        self._lock = asyncio.Lock()

    async def load(self, job_id: str) -> Optional[ProductionState]:
        async with self._lock:
            state = self._states.get(job_id)
            return copy.deepcopy(state) if state is not None else None

    async def save(self, state: ProductionState) -> None:
        async with self._lock:
            self._states[state.job_id] = copy.deepcopy(state)


class MultimodalContentProductionAgent:
    """Recoverable long-horizon workflow for short-video/content production.

    Flow:
        brief -> script -> storyboard -> parallel visual generation
        -> voice -> assembly -> quality gate -> human approval -> publish

    Completed artifacts are checkpointed after every stage. Re-running with
    the same job_id resumes from the latest valid checkpoint instead of
    replaying already completed work.
    """

    def __init__(
        self,
        planner: ContentPlanner,
        media_toolkit: MediaToolkit,
        evaluator: QualityEvaluator,
        checkpoint_store: CheckpointStore,
        approval_gate: Optional[ApprovalGate] = None,
        publisher: Optional[Publisher] = None,
        *,
        require_human_approval: bool = True,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.05,
        max_parallel_shots: int = 4,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if max_parallel_shots < 1:
            raise ValueError("max_parallel_shots must be >= 1")

        self.planner = planner
        self.media_toolkit = media_toolkit
        self.evaluator = evaluator
        self.checkpoint_store = checkpoint_store
        self.approval_gate = approval_gate
        self.publisher = publisher
        self.require_human_approval = require_human_approval
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.max_parallel_shots = max_parallel_shots

    async def run(
        self,
        *,
        brief: Optional[Dict[str, Any]] = None,
        platform: str = "douyin",
        job_id: Optional[str] = None,
        resume: bool = True,
    ) -> ProductionState:
        """Run or resume a production job."""

        if job_id and resume:
            state = await self.checkpoint_store.load(job_id)
        else:
            state = None

        if state is None:
            if not brief:
                raise ValueError("brief is required when creating a new job")
            state = ProductionState(
                job_id=job_id or f"content_{uuid4().hex[:16]}",
                brief=dict(brief),
                platform=platform,
            )

        if state.status == ProductionStatus.COMPLETED:
            return state

        state.status = ProductionStatus.RUNNING
        await self.checkpoint_store.save(state)

        try:
            if not state.script:
                state.stage = ProductionStage.PLAN_SCRIPT
                state.script = await self._call_with_retry(
                    state,
                    ProductionStage.PLAN_SCRIPT.value,
                    lambda: self.planner.create_script(
                        state.brief, state.platform
                    ),
                )
                await self.checkpoint_store.save(state)

            if not state.storyboard:
                state.stage = ProductionStage.BUILD_STORYBOARD
                state.storyboard = await self._call_with_retry(
                    state,
                    ProductionStage.BUILD_STORYBOARD.value,
                    lambda: self.planner.create_storyboard(
                        state.script, state.platform
                    ),
                )
                if not state.storyboard:
                    raise ValueError("planner returned an empty storyboard")
                await self.checkpoint_store.save(state)

            state.stage = ProductionStage.GENERATE_VISUALS
            await self._ensure_visual_assets(state)

            if state.voice_asset is None:
                state.stage = ProductionStage.SYNTHESIZE_VOICE
                state.voice_asset = await self._call_with_retry(
                    state,
                    ProductionStage.SYNTHESIZE_VOICE.value,
                    lambda: self.media_toolkit.synthesize_voice(
                        state.script, self._context(state)
                    ),
                )
                await self.checkpoint_store.save(state)

            if state.final_video is None:
                state.stage = ProductionStage.ASSEMBLE_VIDEO
                state.final_video = await self._call_with_retry(
                    state,
                    ProductionStage.ASSEMBLE_VIDEO.value,
                    lambda: self.media_toolkit.assemble_video(
                        state.storyboard,
                        state.visual_assets,
                        state.voice_asset,
                        self._context(state),
                    ),
                )
                await self.checkpoint_store.save(state)

            if state.quality_report is None:
                state.stage = ProductionStage.QUALITY_GATE
                state.quality_report = await self._call_with_retry(
                    state,
                    ProductionStage.QUALITY_GATE.value,
                    lambda: self.evaluator.evaluate(state),
                )
                await self.checkpoint_store.save(state)

            if not state.quality_report.passed:
                state.status = ProductionStatus.NEEDS_REVISION
                await self.checkpoint_store.save(state)
                return state

            if self.require_human_approval and not state.approved:
                state.stage = ProductionStage.APPROVAL
                if self.approval_gate is None:
                    state.status = ProductionStatus.WAITING_APPROVAL
                    await self.checkpoint_store.save(state)
                    return state

                state.approved = await self._call_with_retry(
                    state,
                    ProductionStage.APPROVAL.value,
                    lambda: self.approval_gate.approve(state),
                )
                if not state.approved:
                    state.status = ProductionStatus.WAITING_APPROVAL
                    await self.checkpoint_store.save(state)
                    return state
                await self.checkpoint_store.save(state)

            if self.publisher is not None and state.publish_result is None:
                state.stage = ProductionStage.PUBLISH
                state.publish_result = await self._call_with_retry(
                    state,
                    ProductionStage.PUBLISH.value,
                    lambda: self.publisher.publish(state),
                )
                await self.checkpoint_store.save(state)

            state.stage = ProductionStage.COMPLETED
            state.status = ProductionStatus.COMPLETED
            await self.checkpoint_store.save(state)
            return state
        except Exception:
            state.status = ProductionStatus.FAILED
            await self.checkpoint_store.save(state)
            raise

    async def approve(self, job_id: str) -> ProductionState:
        """Persist human approval so the job can resume without replaying work."""

        state = await self.checkpoint_store.load(job_id)
        if state is None:
            raise KeyError(f"unknown production job: {job_id}")
        if state.quality_report is None or not state.quality_report.passed:
            raise ValueError("job has not passed the quality gate")

        state.approved = True
        state.status = ProductionStatus.PENDING
        await self.checkpoint_store.save(state)
        return state

    async def _ensure_visual_assets(self, state: ProductionState) -> None:
        semaphore = asyncio.Semaphore(self.max_parallel_shots)
        state_lock = asyncio.Lock()

        async def generate_one(shot: StoryboardShot) -> None:
            if shot.shot_id in state.visual_assets:
                return

            async with semaphore:
                asset = await self._call_with_retry(
                    state,
                    f"{ProductionStage.GENERATE_VISUALS.value}:{shot.shot_id}",
                    lambda: self.media_toolkit.generate_visual(
                        shot, self._context(state)
                    ),
                )

            async with state_lock:
                state.visual_assets[shot.shot_id] = asset
                await self.checkpoint_store.save(state)

        await asyncio.gather(*(generate_one(shot) for shot in state.storyboard))

    async def _call_with_retry(self, state: ProductionState, key: str, operation):
        last_error: Optional[Exception] = None

        for retry_index in range(self.max_retries + 1):
            state.attempts[key] = state.attempts.get(key, 0) + 1
            try:
                return await operation()
            except Exception as exc:
                last_error = exc
                state.errors.append(
                    {
                        "stage": key,
                        "attempt": state.attempts[key],
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                )
                await self.checkpoint_store.save(state)

                if retry_index >= self.max_retries:
                    raise

                await asyncio.sleep(
                    self.retry_backoff_seconds * (2**retry_index)
                )

        if last_error is not None:  # pragma: no cover
            raise last_error
        raise RuntimeError("retry loop exited without result")  # pragma: no cover

    @staticmethod
    def _context(state: ProductionState) -> Dict[str, Any]:
        return {
            "job_id": state.job_id,
            "brief": state.brief,
            "platform": state.platform,
            "script": state.script,
        }
