"""Concrete media providers for the multimodal production runtime."""

from __future__ import annotations

import asyncio
import logging
import math
import random
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from .multimodal_content_workflow import (
    AssetKind,
    MediaAsset,
    MediaToolkit,
    StoryboardShot,
)

logger = logging.getLogger(__name__)


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in value)


def _local_path(uri: str) -> Path:
    if uri.startswith("file://"):
        return Path(uri[7:])
    if "://" in uri:
        raise ValueError(f"FFmpeg requires a local/file URI, got: {uri}")
    return Path(uri)


class RunwayVideoGenerator:
    """Runway Gen-4.5 text/image-to-video adapter.

    The adapter uses Runway's asynchronous task API and downloads ephemeral
    output URLs into durable local artifacts before returning.
    """

    def __init__(
        self,
        *,
        api_secret: str,
        output_dir: str,
        api_base: str = "https://api.dev.runwayml.com",
        api_version: str = "2024-11-06",
        model: str = "gen4.5",
        ratio: str = "720:1280",
        request_timeout_seconds: float = 60.0,
        task_timeout_seconds: float = 600.0,
        poll_interval_seconds: float = 5.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        if not api_secret:
            raise ValueError("Runway API secret is required")
        self.api_secret = api_secret
        self.output_dir = Path(output_dir)
        self.api_base = api_base.rstrip("/")
        self.api_version = api_version
        self.model = model
        self.ratio = ratio
        self.request_timeout_seconds = request_timeout_seconds
        self.task_timeout_seconds = task_timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self._client = client

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_secret}",
            "Content-Type": "application/json",
            "X-Runway-Version": self.api_version,
        }

    async def generate(
        self,
        shot: StoryboardShot,
        context: Dict[str, Any],
    ) -> MediaAsset:
        job_id = str(context["job_id"])
        artifact_dir = self.output_dir / _safe_name(job_id) / "visuals"
        artifact_dir.mkdir(parents=True, exist_ok=True)

        duration = max(2, min(10, int(math.ceil(shot.duration_seconds))))
        payload: Dict[str, Any] = {
            "model": self.model,
            "promptText": shot.visual_prompt,
            "ratio": self.ratio,
            "duration": duration,
        }

        prompt_image = shot.metadata.get("prompt_image_url")
        if prompt_image:
            payload["promptImage"] = prompt_image

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.request_timeout_seconds)
        try:
            response = await client.post(
                f"{self.api_base}/v1/image_to_video",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            task_id = str(response.json()["id"])

            task = await self._wait_for_task(client, task_id)
            outputs = task.get("output") or []
            if not outputs:
                raise RuntimeError(f"Runway task {task_id} succeeded without output")

            output_url = str(outputs[0])
            video_response = await client.get(
                output_url,
                timeout=self.request_timeout_seconds,
            )
            video_response.raise_for_status()

            output_path = artifact_dir / f"{_safe_name(shot.shot_id)}.mp4"
            output_path.write_bytes(video_response.content)

            return MediaAsset(
                asset_id=f"runway-{task_id}",
                kind=AssetKind.VIDEO,
                uri=str(output_path),
                provider="runway",
                metadata={
                    "task_id": task_id,
                    "model": self.model,
                    "requested_duration_seconds": shot.duration_seconds,
                    "generated_duration_seconds": duration,
                    "ratio": self.ratio,
                },
            )
        finally:
            if owns_client:
                await client.aclose()

    async def _wait_for_task(
        self,
        client: httpx.AsyncClient,
        task_id: str,
    ) -> Dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + self.task_timeout_seconds
        sleep_seconds = max(self.poll_interval_seconds, 0.0)

        while True:
            response = await client.get(
                f"{self.api_base}/v1/tasks/{task_id}",
                headers=self.headers,
            )
            response.raise_for_status()
            task = response.json()
            status = str(task.get("status") or "").upper()

            if status == "SUCCEEDED":
                return task
            if status in {"FAILED", "CANCELED", "CANCELLED"}:
                raise RuntimeError(
                    f"Runway task {task_id} ended with status={status}: "
                    f"{task.get('failure') or task.get('error') or task}"
                )
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError(f"Runway task {task_id} timed out")

            jitter = random.uniform(0.0, min(1.0, sleep_seconds * 0.2))
            await asyncio.sleep(sleep_seconds + jitter)


class ElevenLabsTTSGenerator:
    """ElevenLabs synchronous text-to-speech adapter."""

    def __init__(
        self,
        *,
        api_key: str,
        voice_id: str,
        output_dir: str,
        api_base: str = "https://api.elevenlabs.io",
        model_id: str = "eleven_multilingual_v2",
        output_format: str = "mp3_44100_128",
        request_timeout_seconds: float = 120.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        if not api_key:
            raise ValueError("ElevenLabs API key is required")
        if not voice_id:
            raise ValueError("ElevenLabs voice_id is required")
        self.api_key = api_key
        self.voice_id = voice_id
        self.output_dir = Path(output_dir)
        self.api_base = api_base.rstrip("/")
        self.model_id = model_id
        self.output_format = output_format
        self.request_timeout_seconds = request_timeout_seconds
        self._client = client

    async def synthesize(
        self,
        script: Dict[str, Any],
        context: Dict[str, Any],
    ) -> MediaAsset:
        narration = str(
            script.get("narration") or script.get("body") or script.get("title") or ""
        ).strip()
        if not narration:
            raise ValueError("script must contain narration/body/title for TTS")

        job_id = str(context["job_id"])
        artifact_dir = self.output_dir / _safe_name(job_id) / "audio"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        output_path = artifact_dir / "narration.mp3"

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=self.request_timeout_seconds
        )
        try:
            response = await client.post(
                f"{self.api_base}/v1/text-to-speech/{self.voice_id}",
                params={"output_format": self.output_format},
                headers={
                    "xi-api-key": self.api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json={
                    "text": narration,
                    "model_id": self.model_id,
                },
            )
            response.raise_for_status()
            output_path.write_bytes(response.content)

            return MediaAsset(
                asset_id=f"elevenlabs-{_safe_name(job_id)}",
                kind=AssetKind.AUDIO,
                uri=str(output_path),
                provider="elevenlabs",
                metadata={
                    "voice_id": self.voice_id,
                    "model_id": self.model_id,
                    "output_format": self.output_format,
                    "request_id": response.headers.get("request-id"),
                    "trace_id": response.headers.get("x-trace-id"),
                    "character_cost": response.headers.get("character-cost"),
                },
            )
        finally:
            if owns_client:
                await client.aclose()


class FFmpegVideoAssembler:
    """Deterministic FFmpeg assembler for vertical short-form video."""

    def __init__(
        self,
        *,
        output_dir: str,
        ffmpeg_bin: str = "ffmpeg",
        width: int = 720,
        height: int = 1280,
        fps: int = 30,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.ffmpeg_bin = ffmpeg_bin
        self.width = width
        self.height = height
        self.fps = fps

    async def assemble(
        self,
        storyboard: List[StoryboardShot],
        visual_assets: Dict[str, MediaAsset],
        voice_asset: MediaAsset,
        context: Dict[str, Any],
    ) -> MediaAsset:
        if shutil.which(self.ffmpeg_bin) is None:
            raise RuntimeError(f"FFmpeg binary not found: {self.ffmpeg_bin}")
        if not storyboard:
            raise ValueError("storyboard is empty")

        job_id = str(context["job_id"])
        work_dir = self.output_dir / _safe_name(job_id) / "assembly"
        work_dir.mkdir(parents=True, exist_ok=True)

        normalized_paths: List[Path] = []
        for index, shot in enumerate(storyboard):
            asset = visual_assets.get(shot.shot_id)
            if asset is None:
                raise ValueError(f"missing visual asset for shot {shot.shot_id}")
            source = _local_path(asset.uri)
            if not source.exists():
                raise FileNotFoundError(source)

            normalized = work_dir / f"shot_{index:03d}.mp4"
            await self._normalize_clip(
                source,
                normalized,
                duration_seconds=max(shot.duration_seconds, 0.5),
            )
            normalized_paths.append(normalized)

        concat_file = work_dir / "concat.txt"
        concat_file.write_text(
            "\n".join(
                f"file '{path.as_posix().replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'"
                for path in normalized_paths
            )
            + "\n",
            encoding="utf-8",
        )

        merged_path = work_dir / "merged_video.mp4"
        await self._run(
            self.ffmpeg_bin,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(merged_path),
        )

        voice_path = _local_path(voice_asset.uri)
        if not voice_path.exists():
            raise FileNotFoundError(voice_path)

        final_path = work_dir / "final.mp4"
        await self._run(
            self.ffmpeg_bin,
            "-y",
            "-i",
            str(merged_path),
            "-i",
            str(voice_path),
            "-filter_complex",
            "[1:a]apad[a]",
            "-map",
            "0:v:0",
            "-map",
            "[a]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            "-movflags",
            "+faststart",
            str(final_path),
        )

        return MediaAsset(
            asset_id=f"ffmpeg-{_safe_name(job_id)}",
            kind=AssetKind.FINAL_VIDEO,
            uri=str(final_path),
            provider="ffmpeg",
            metadata={
                "width": self.width,
                "height": self.height,
                "fps": self.fps,
                "shot_count": len(storyboard),
            },
        )

    async def _normalize_clip(
        self,
        source: Path,
        output: Path,
        *,
        duration_seconds: float,
    ) -> None:
        video_filter = (
            f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,"
            f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2,"
            f"setsar=1,fps={self.fps}"
        )
        await self._run(
            self.ffmpeg_bin,
            "-y",
            "-i",
            str(source),
            "-t",
            f"{duration_seconds:.3f}",
            "-vf",
            video_filter,
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            str(output),
        )

    async def _run(self, *args: str) -> None:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(
                "FFmpeg command failed: "
                + " ".join(args)
                + "\n"
                + stderr.decode("utf-8", errors="replace")[-4000:]
            )
        if stdout:
            logger.debug(
                "ffmpeg stdout: %s",
                stdout.decode("utf-8", errors="replace")[-1000:],
            )


class ProductionMediaToolkit(MediaToolkit):
    """Composition of video generation, TTS, and deterministic assembly."""

    def __init__(
        self,
        *,
        video_generator: RunwayVideoGenerator,
        tts_generator: ElevenLabsTTSGenerator,
        assembler: FFmpegVideoAssembler,
    ) -> None:
        self.video_generator = video_generator
        self.tts_generator = tts_generator
        self.assembler = assembler

    async def generate_visual(
        self,
        shot: StoryboardShot,
        context: Dict[str, Any],
    ) -> MediaAsset:
        return await self.video_generator.generate(shot, context)

    async def synthesize_voice(
        self,
        script: Dict[str, Any],
        context: Dict[str, Any],
    ) -> MediaAsset:
        return await self.tts_generator.synthesize(script, context)

    async def assemble_video(
        self,
        storyboard: List[StoryboardShot],
        visual_assets: Dict[str, MediaAsset],
        voice_asset: MediaAsset,
        context: Dict[str, Any],
    ) -> MediaAsset:
        return await self.assembler.assemble(
            storyboard,
            visual_assets,
            voice_asset,
            context,
        )
