"""Evaluation harness for multimodal production jobs."""

from __future__ import annotations

import asyncio
import base64
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from openai import AsyncOpenAI

from .multimodal_content_workflow import ProductionState, QualityReport


class MultimodalJudge(Protocol):
    async def evaluate(self, state: ProductionState) -> Dict[str, Any]:
        """Return optional model-based review signals."""


class OpenAIMultimodalJudge:
    """Vision-language judge over sampled frames from the assembled video.

    The judge is advisory: deterministic artifact integrity checks remain the
    hard gate in MultimodalEvaluationHarness.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-6-astra",
        ffmpeg_bin: str = "ffmpeg",
        sample_count: int = 4,
        client: Optional[Any] = None,
    ) -> None:
        if not api_key:
            raise ValueError("OpenAI API key is required for multimodal judging")
        if sample_count < 1:
            raise ValueError("sample_count must be >= 1")
        self.model = model
        self.ffmpeg_bin = ffmpeg_bin
        self.sample_count = sample_count
        self.client = client or AsyncOpenAI(api_key=api_key)

    async def evaluate(self, state: ProductionState) -> Dict[str, Any]:
        if state.final_video is None:
            raise ValueError("final video is required for multimodal judging")

        video_path = MultimodalEvaluationHarness._local_path(state.final_video.uri)
        if not video_path.exists():
            raise FileNotFoundError(video_path)

        with tempfile.TemporaryDirectory(prefix="multimodal-judge-") as tmp:
            frame_paths = await self._sample_frames(
                video_path,
                Path(tmp),
                state,
            )
            content: List[Dict[str, Any]] = [
                {
                    "type": "input_text",
                    "text": self._build_prompt(state),
                }
            ]
            for frame_path in frame_paths:
                encoded = base64.b64encode(frame_path.read_bytes()).decode("ascii")
                content.append(
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{encoded}",
                        "detail": "auto",
                    }
                )

            response = await self.client.responses.create(
                model=self.model,
                input=[{"role": "user", "content": content}],
            )
            raw = str(response.output_text or "").strip()
            result = self._parse_json(raw)
            score = max(0.0, min(1.0, float(result.get("score", 0.0))))
            return {
                "score": score,
                "issues": list(result.get("issues") or []),
                "dimensions": dict(result.get("dimensions") or {}),
                "reasoning": str(result.get("reasoning") or ""),
                "sampled_frames": len(frame_paths),
                "model": self.model,
            }

    async def _sample_frames(
        self,
        video_path: Path,
        output_dir: Path,
        state: ProductionState,
    ) -> List[Path]:
        total_duration = sum(
            max(float(shot.duration_seconds), 0.5) for shot in state.storyboard
        )
        if total_duration <= 0:
            total_duration = 1.0

        timestamps = [
            total_duration * (index + 1) / (self.sample_count + 1)
            for index in range(self.sample_count)
        ]
        paths: List[Path] = []
        for index, timestamp in enumerate(timestamps):
            output = output_dir / f"frame_{index:02d}.jpg"
            process = await asyncio.create_subprocess_exec(
                self.ffmpeg_bin,
                "-y",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-q:v",
                "3",
                str(output),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()
            if process.returncode != 0 or not output.exists():
                raise RuntimeError(
                    "failed to sample video frame: "
                    + stderr.decode("utf-8", errors="replace")[-2000:]
                )
            paths.append(output)
        return paths

    @staticmethod
    def _build_prompt(state: ProductionState) -> str:
        storyboard = [
            {
                "shot_id": shot.shot_id,
                "narration": shot.narration,
                "visual_prompt": shot.visual_prompt,
                "duration_seconds": shot.duration_seconds,
            }
            for shot in state.storyboard
        ]
        return (
            "Evaluate the sampled frames from a generated short-form video "
            "against the intended script and storyboard. Judge only visible "
            "evidence and the supplied plan. Assess visual-story consistency, "
            "shot relevance, obvious visual defects, brand/factual mismatch, "
            "and overall publish readiness. Return JSON only with: "
            '{"score": 0.0-1.0, "issues": ["..."], '
            '"dimensions": {"visual_story_alignment": 0.0-1.0, '
            '"visual_quality": 0.0-1.0, "publish_readiness": 0.0-1.0}, '
            '"reasoning": "brief explanation"}. '
            f"Script: {json.dumps(state.script, ensure_ascii=False)}. "
            f"Storyboard: {json.dumps(storyboard, ensure_ascii=False)}."
        )

    @staticmethod
    def _parse_json(raw: str) -> Dict[str, Any]:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                return json.loads(raw[start : end + 1])
            raise


@dataclass
class EvalThresholds:
    minimum_score: float = 0.8
    duration_tolerance_seconds: float = 2.0
    require_audio: bool = True
    require_video: bool = True


class MultimodalEvaluationHarness:
    """Deterministic checks plus an optional model-based judge.

    Deterministic checks stay authoritative for artifact integrity. An optional
    multimodal judge can contribute a bounded semantic-quality score, but it
    cannot override missing assets, missing streams, or broken artifacts.
    """

    def __init__(
        self,
        *,
        ffprobe_bin: str = "ffprobe",
        thresholds: Optional[EvalThresholds] = None,
        judge: Optional[MultimodalJudge] = None,
    ) -> None:
        self.ffprobe_bin = ffprobe_bin
        self.thresholds = thresholds or EvalThresholds()
        self.judge = judge

    async def evaluate(self, state: ProductionState) -> QualityReport:
        issues = []
        dimensions: Dict[str, float] = {}

        script_score = self._script_score(state)
        dimensions["script_completeness"] = script_score
        if script_score < 1.0:
            issues.append("script_incomplete")

        coverage_score = self._asset_coverage_score(state)
        dimensions["storyboard_asset_coverage"] = coverage_score
        if coverage_score < 1.0:
            issues.append("missing_storyboard_assets")

        artifact_score = 0.0
        media_probe: Dict[str, Any] = {}
        if state.final_video is None:
            issues.append("final_video_missing")
        else:
            try:
                path = self._local_path(state.final_video.uri)
                if not path.exists() or path.stat().st_size <= 0:
                    issues.append("final_video_file_missing_or_empty")
                else:
                    media_probe = await self._probe(path)
                    artifact_score = self._artifact_score(media_probe, state, issues)
            except Exception as exc:
                issues.append(f"final_video_probe_failed:{type(exc).__name__}")

        dimensions["artifact_integrity"] = artifact_score

        judge_score: Optional[float] = None
        judge_metadata: Dict[str, Any] = {}
        if self.judge is not None and artifact_score > 0:
            try:
                judge_result = await self.judge.evaluate(state)
                judge_score = max(
                    0.0,
                    min(1.0, float(judge_result.get("score", 0.0))),
                )
                judge_metadata = dict(judge_result)
                dimensions["multimodal_judge"] = judge_score
                for issue in judge_result.get("issues", []) or []:
                    issues.append(f"judge:{issue}")
            except Exception as exc:
                issues.append(f"judge_failed:{type(exc).__name__}")

        base_score = (
            dimensions["script_completeness"] * 0.2
            + dimensions["storyboard_asset_coverage"] * 0.25
            + dimensions["artifact_integrity"] * 0.55
        )
        score = base_score
        if judge_score is not None:
            score = base_score * 0.8 + judge_score * 0.2

        hard_failure = any(
            issue.startswith(
                (
                    "final_video_missing",
                    "final_video_file_missing",
                    "final_video_probe_failed",
                    "missing_video_stream",
                    "missing_audio_stream",
                )
            )
            for issue in issues
        )
        passed = (
            not hard_failure
            and coverage_score == 1.0
            and score >= self.thresholds.minimum_score
        )

        return QualityReport(
            score=round(score, 4),
            passed=passed,
            issues=issues,
            metadata={
                "dimensions": dimensions,
                "media_probe": media_probe,
                "judge": judge_metadata,
            },
        )

    @staticmethod
    def _script_score(state: ProductionState) -> float:
        required = ("title", "hook", "body", "cta")
        present = sum(
            bool(str(state.script.get(key) or "").strip()) for key in required
        )
        return present / len(required)

    @staticmethod
    def _asset_coverage_score(state: ProductionState) -> float:
        if not state.storyboard:
            return 0.0
        covered = sum(
            1 for shot in state.storyboard if shot.shot_id in state.visual_assets
        )
        return covered / len(state.storyboard)

    def _artifact_score(
        self,
        probe: Dict[str, Any],
        state: ProductionState,
        issues: list[str],
    ) -> float:
        streams = probe.get("streams") or []
        format_info = probe.get("format") or {}

        video_streams = [
            stream for stream in streams if stream.get("codec_type") == "video"
        ]
        audio_streams = [
            stream for stream in streams if stream.get("codec_type") == "audio"
        ]

        score = 1.0
        if self.thresholds.require_video and not video_streams:
            issues.append("missing_video_stream")
            score -= 0.6
        if self.thresholds.require_audio and not audio_streams:
            issues.append("missing_audio_stream")
            score -= 0.25

        target_duration = sum(
            max(float(shot.duration_seconds), 0.0) for shot in state.storyboard
        )
        actual_duration = float(format_info.get("duration") or 0.0)
        if target_duration > 0 and actual_duration > 0:
            if (
                abs(actual_duration - target_duration)
                > self.thresholds.duration_tolerance_seconds
            ):
                issues.append(
                    "duration_mismatch:"
                    f"actual={actual_duration:.2f},target={target_duration:.2f}"
                )
                score -= 0.15
        elif target_duration > 0:
            issues.append("duration_unknown")
            score -= 0.1

        return max(0.0, min(1.0, score))

    async def _probe(self, path: Path) -> Dict[str, Any]:
        process = await asyncio.create_subprocess_exec(
            self.ffprobe_bin,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(stderr.decode("utf-8", errors="replace")[-2000:])
        return json.loads(stdout.decode("utf-8"))

    @staticmethod
    def _local_path(uri: str) -> Path:
        if uri.startswith("file://"):
            return Path(uri[7:])
        if "://" in uri:
            raise ValueError("evaluation requires a durable local/file artifact URI")
        return Path(uri)
