"""Concrete media providers for the multimodal production runtime."""

from __future__ import annotations

import asyncio
import logging
import math
import random
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from .multimodal_artifacts import ArtifactStore
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


@dataclass
class BrandTemplate:
    """Optional visual template for owned/non-TikTok distribution."""

    text: str = ""
    font_name: str = "DejaVu Sans"
    font_size: int = 28
    margin_x: int = 32
    margin_y: int = 32
    opacity: float = 0.82


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
        client = self._client or httpx.AsyncClient(timeout=self.request_timeout_seconds)
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
        render_subtitles: bool = True,
        subtitle_font_name: str = "DejaVu Sans",
        subtitle_font_size: int = 26,
        brand_template: Optional[BrandTemplate] = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.ffmpeg_bin = ffmpeg_bin
        self.width = width
        self.height = height
        self.fps = fps
        self.render_subtitles = render_subtitles
        self.subtitle_font_name = subtitle_font_name
        self.subtitle_font_size = subtitle_font_size
        self.brand_template = brand_template

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
        subtitle_path = None
        if self.render_subtitles:
            subtitle_path = work_dir / "subtitles.srt"
            self._write_srt(storyboard, subtitle_path)

        platform = str(context.get("platform") or "").lower()
        brand_applied = (
            self.brand_template is not None
            and bool(self.brand_template.text.strip())
            and platform != "tiktok"
        )
        video_filter = self._build_final_video_filter(
            subtitle_path=subtitle_path,
            brand_applied=brand_applied,
        )

        filter_complex = "[1:a]apad[a]"
        map_video = "0:v:0"
        video_codec = "copy"
        if video_filter:
            filter_complex = f"[0:v]{video_filter}[v];[1:a]apad[a]"
            map_video = "[v]"
            video_codec = "libx264"

        await self._run(
            self.ffmpeg_bin,
            "-y",
            "-i",
            str(merged_path),
            "-i",
            str(voice_path),
            "-filter_complex",
            filter_complex,
            "-map",
            map_video,
            "-map",
            "[a]",
            "-c:v",
            video_codec,
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
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
                "subtitles_rendered": bool(subtitle_path),
                "brand_template_applied": brand_applied,
                "brand_template_suppressed_for_tiktok": (
                    self.brand_template is not None and platform == "tiktok"
                ),
            },
        )

    def _build_final_video_filter(
        self,
        *,
        subtitle_path: Optional[Path],
        brand_applied: bool,
    ) -> str:
        filters: List[str] = []

        if subtitle_path is not None:
            escaped_path = self._escape_filter_path(subtitle_path)
            style = (
                f"FontName={self.subtitle_font_name},"
                f"FontSize={self.subtitle_font_size},"
                "PrimaryColour=&H00FFFFFF,"
                "OutlineColour=&H80000000,"
                "BorderStyle=1,Outline=2,Shadow=0,"
                "Alignment=2,MarginV=72"
            )
            filters.append(
                f"subtitles='{escaped_path}':force_style='{style}'"
            )

        if brand_applied and self.brand_template is not None:
            brand = self.brand_template
            text = self._escape_drawtext(brand.text)
            filters.append(
                "drawtext="
                f"text='{text}':"
                f"font='{self._escape_drawtext(brand.font_name)}':"
                f"fontsize={brand.font_size}:"
                f"fontcolor=white@{max(0.0, min(1.0, brand.opacity)):.2f}:"
                f"x=w-tw-{brand.margin_x}:"
                f"y=h-th-{brand.margin_y}"
            )

        return ",".join(filters)

    @staticmethod
    def _write_srt(
        storyboard: List[StoryboardShot],
        path: Path,
    ) -> None:
        lines: List[str] = []
        cursor = 0.0
        for index, shot in enumerate(storyboard, start=1):
            start = cursor
            end = cursor + max(float(shot.duration_seconds), 0.5)
            cursor = end
            text = (shot.narration or "").strip()
            if not text:
                continue
            lines.extend(
                [
                    str(index),
                    f"{FFmpegVideoAssembler._srt_time(start)} --> "
                    f"{FFmpegVideoAssembler._srt_time(end)}",
                    text.replace("\n", " "),
                    "",
                ]
            )
        path.write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _srt_time(seconds: float) -> str:
        total_ms = max(0, int(round(seconds * 1000)))
        hours, remainder = divmod(total_ms, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        secs, milliseconds = divmod(remainder, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

    @staticmethod
    def _escape_filter_path(path: Path) -> str:
        value = path.as_posix()
        return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

    @staticmethod
    def _escape_drawtext(value: str) -> str:
        return (
            value.replace("\\", "\\\\")
            .replace(":", "\\:")
            .replace("'", "\\'")
            .replace("%", "\\%")
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
        artifact_store: Optional[ArtifactStore] = None,
    ) -> None:
        self.video_generator = video_generator
        self.tts_generator = tts_generator
        self.assembler = assembler
        self.artifact_store = artifact_store

    async def generate_visual(
        self,
        shot: StoryboardShot,
        context: Dict[str, Any],
    ) -> MediaAsset:
        asset = await self.video_generator.generate(shot, context)
        if self.artifact_store is not None:
            asset = await self.artifact_store.persist(
                asset,
                job_id=str(context["job_id"]),
                category="visuals",
            )
        return asset

    async def synthesize_voice(
        self,
        script: Dict[str, Any],
        context: Dict[str, Any],
    ) -> MediaAsset:
        asset = await self.tts_generator.synthesize(script, context)
        if self.artifact_store is not None:
            asset = await self.artifact_store.persist(
                asset,
                job_id=str(context["job_id"]),
                category="audio",
            )
        return asset

    async def assemble_video(
        self,
        storyboard: List[StoryboardShot],
        visual_assets: Dict[str, MediaAsset],
        voice_asset: MediaAsset,
        context: Dict[str, Any],
    ) -> MediaAsset:
        resolved_visuals = visual_assets
        resolved_voice = voice_asset
        if self.artifact_store is not None:
            resolved_visuals = {
                shot_id: await self.artifact_store.materialize(asset)
                for shot_id, asset in visual_assets.items()
            }
            resolved_voice = await self.artifact_store.materialize(voice_asset)

        asset = await self.assembler.assemble(
            storyboard,
            resolved_visuals,
            resolved_voice,
            context,
        )
        if self.artifact_store is not None:
            asset = await self.artifact_store.persist(
                asset,
                job_id=str(context["job_id"]),
                category="final",
            )
        return asset
