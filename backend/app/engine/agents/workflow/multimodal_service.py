"""Background job service for multimodal content production."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional
from uuid import uuid4

from app.core.config import get_settings
from app.engine.llm.providers.unified_adapter import UnifiedLLMProviderAdapter

from .multimodal_artifacts import MinIOArtifactStore
from .multimodal_content_adapters import LLMContentPlanner
from .multimodal_content_workflow import (
    MultimodalContentProductionAgent,
    ProductionState,
)
from .multimodal_eval import MultimodalEvaluationHarness
from .multimodal_media import (
    ElevenLabsTTSGenerator,
    FFmpegVideoAssembler,
    ProductionMediaToolkit,
    RunwayVideoGenerator,
)
from .multimodal_persistence import SQLAlchemyCheckpointStore


logger = logging.getLogger(__name__)


class MultimodalProductionService:
    """Runs durable production jobs while keeping active-task state in-process."""

    def __init__(
        self,
        agent: MultimodalContentProductionAgent,
        checkpoint_store: SQLAlchemyCheckpointStore,
    ) -> None:
        self.agent = agent
        self.checkpoint_store = checkpoint_store
        self._tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def submit(
        self,
        *,
        brief: Dict[str, Any],
        platform: str,
        owner_id: str,
        job_id: Optional[str] = None,
    ) -> str:
        resolved_job_id = job_id or f"content_{uuid4().hex[:16]}"
        existing = await self.checkpoint_store.load(resolved_job_id)
        if existing is not None:
            raise ValueError(f"job already exists: {resolved_job_id}")

        initial_state = ProductionState(
            job_id=resolved_job_id,
            brief=dict(brief),
            platform=platform,
            metadata={"owner_id": owner_id},
        )
        await self.checkpoint_store.save(initial_state)

        try:
            await self._start(
                resolved_job_id,
                brief=None,
                platform=platform,
                owner_id=owner_id,
                resume=True,
            )
        except Exception:
            # The accepted job checkpoint intentionally remains queryable even
            # when scheduling fails; callers can inspect or resume it.
            raise
        return resolved_job_id

    async def resume(self, job_id: str) -> None:
        state = await self.checkpoint_store.load(job_id)
        if state is None:
            raise KeyError(job_id)
        await self._start(
            job_id,
            brief=None,
            platform=state.platform,
            owner_id=str(state.metadata.get("owner_id") or ""),
            resume=True,
        )

    async def approve(self, job_id: str) -> ProductionState:
        state = await self.agent.approve(job_id)
        await self.resume(job_id)
        return state

    async def cancel(self, job_id: str) -> ProductionState:
        async with self._lock:
            task = self._tasks.get(job_id)
            if task is not None and not task.done():
                task.cancel()

        try:
            return await self.agent.cancel(job_id)
        finally:
            async with self._lock:
                self._tasks.pop(job_id, None)

    async def status(self, job_id: str) -> Optional[ProductionState]:
        return await self.checkpoint_store.load(job_id)

    async def _start(
        self,
        job_id: str,
        *,
        brief: Optional[Dict[str, Any]],
        platform: str,
        owner_id: str,
        resume: bool,
    ) -> None:
        async with self._lock:
            current = self._tasks.get(job_id)
            if current is not None and not current.done():
                raise RuntimeError(f"job is already running: {job_id}")

            task = asyncio.create_task(
                self._run_job(
                    job_id,
                    brief=brief,
                    platform=platform,
                    owner_id=owner_id,
                    resume=resume,
                ),
                name=f"multimodal-production:{job_id}",
            )
            self._tasks[job_id] = task
            task.add_done_callback(
                lambda completed, key=job_id: asyncio.create_task(
                    self._remove_task(key, completed)
                )
            )

    async def _run_job(
        self,
        job_id: str,
        *,
        brief: Optional[Dict[str, Any]],
        platform: str,
        owner_id: str,
        resume: bool,
    ) -> None:
        await self.agent.run(
            brief=brief,
            platform=platform,
            job_id=job_id,
            resume=resume,
            metadata={"owner_id": owner_id},
        )

    async def _remove_task(self, job_id: str, task: asyncio.Task) -> None:
        try:
            if task.cancelled():
                logger.info("multimodal production job cancelled: %s", job_id)
            else:
                error = task.exception()
                if error is not None:
                    logger.error(
                        "multimodal production job failed: %s: %s",
                        job_id,
                        error,
                    )
        finally:
            async with self._lock:
                if self._tasks.get(job_id) is task:
                    self._tasks.pop(job_id, None)


_service: Optional[MultimodalProductionService] = None
_store: Optional[SQLAlchemyCheckpointStore] = None


def get_multimodal_checkpoint_store() -> SQLAlchemyCheckpointStore:
    global _store
    if _store is None:
        _store = SQLAlchemyCheckpointStore()
    return _store


def get_multimodal_production_service() -> MultimodalProductionService:
    """Build the real provider stack lazily so normal app startup stays cheap."""

    global _service
    if _service is not None:
        return _service

    settings = get_settings()
    missing = []
    if not settings.RUNWAYML_API_SECRET:
        missing.append("RUNWAYML_API_SECRET")
    if not settings.ELEVENLABS_API_KEY:
        missing.append("ELEVENLABS_API_KEY")
    if not settings.ELEVENLABS_VOICE_ID:
        missing.append("ELEVENLABS_VOICE_ID")
    if missing:
        raise RuntimeError(
            "multimodal production providers are not configured: " + ", ".join(missing)
        )

    llm = UnifiedLLMProviderAdapter(
        provider=settings.MULTIMODAL_LLM_PROVIDER,
        model=settings.MULTIMODAL_LLM_MODEL,
        temperature=0.4,
        max_tokens=4096,
    )
    planner = LLMContentPlanner(
        llm,
        model=settings.MULTIMODAL_LLM_MODEL,
        temperature=0.4,
    )

    video_generator = RunwayVideoGenerator(
        api_secret=settings.RUNWAYML_API_SECRET,
        output_dir=settings.MULTIMODAL_ARTIFACT_DIR,
        api_base=settings.RUNWAYML_API_BASE,
        api_version=settings.RUNWAYML_API_VERSION,
        model=settings.RUNWAYML_MODEL,
        ratio=settings.RUNWAYML_RATIO,
    )
    tts_generator = ElevenLabsTTSGenerator(
        api_key=settings.ELEVENLABS_API_KEY,
        voice_id=settings.ELEVENLABS_VOICE_ID,
        output_dir=settings.MULTIMODAL_ARTIFACT_DIR,
        api_base=settings.ELEVENLABS_API_BASE,
        model_id=settings.ELEVENLABS_MODEL_ID,
    )
    assembler = FFmpegVideoAssembler(
        output_dir=settings.MULTIMODAL_ARTIFACT_DIR,
        ffmpeg_bin=settings.FFMPEG_BIN,
    )
    artifact_store = None
    if settings.MULTIMODAL_DURABLE_STORAGE_ENABLED:
        artifact_store = MinIOArtifactStore(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            bucket=settings.MULTIMODAL_ARTIFACT_BUCKET,
            cache_dir=settings.MULTIMODAL_ARTIFACT_DIR,
            secure=settings.MINIO_SECURE,
        )

    media_toolkit = ProductionMediaToolkit(
        video_generator=video_generator,
        tts_generator=tts_generator,
        assembler=assembler,
        artifact_store=artifact_store,
    )

    checkpoint_store = get_multimodal_checkpoint_store()
    evaluator = MultimodalEvaluationHarness(
        ffprobe_bin=settings.FFPROBE_BIN,
    )
    agent = MultimodalContentProductionAgent(
        planner=planner,
        media_toolkit=media_toolkit,
        evaluator=evaluator,
        checkpoint_store=checkpoint_store,
        approval_gate=None,
        publisher=None,
        require_human_approval=True,
        max_retries=2,
        retry_backoff_seconds=1.0,
        max_parallel_shots=3,
    )
    _service = MultimodalProductionService(agent, checkpoint_store)
    return _service
