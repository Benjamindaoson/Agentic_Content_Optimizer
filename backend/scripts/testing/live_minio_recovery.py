"""Live MinIO durability/recovery validation using a real FFmpeg artifact."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path

from app.engine.agents.workflow.multimodal_artifacts import MinIOArtifactStore
from app.engine.agents.workflow.multimodal_content_workflow import (
    AssetKind,
    MediaAsset,
)


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


async def run_ffmpeg(output: Path) -> None:
    process = await asyncio.create_subprocess_exec(
        os.getenv("FFMPEG_BIN", "ffmpeg"),
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=720x1280:rate=30",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=44100",
        "-t",
        "2",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(output),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(
            "FFmpeg test artifact generation failed: "
            + stderr.decode("utf-8", errors="replace")[-3000:]
        )


async def ffprobe(output: Path) -> dict:
    process = await asyncio.create_subprocess_exec(
        os.getenv("FFPROBE_BIN", "ffprobe"),
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(output),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(
            "FFprobe validation failed: "
            + stderr.decode("utf-8", errors="replace")[-3000:]
        )
    return json.loads(stdout.decode("utf-8"))


async def main() -> None:
    if os.getenv("RUN_LIVE_MINIO_RECOVERY") != "1":
        raise RuntimeError(
            "live MinIO recovery disabled; set RUN_LIVE_MINIO_RECOVERY=1"
        )

    root = Path(
        os.getenv(
            "MULTIMODAL_ARTIFACT_DIR",
            "runtime/minio-recovery-validation",
        )
    )
    root.mkdir(parents=True, exist_ok=True)
    source = root / "source.mp4"
    await run_ffmpeg(source)

    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    store = MinIOArtifactStore(
        endpoint=required("MINIO_ENDPOINT"),
        access_key=required("MINIO_ACCESS_KEY"),
        secret_key=required("MINIO_SECRET_KEY"),
        bucket=os.getenv("MULTIMODAL_ARTIFACT_BUCKET", "videos"),
        cache_dir=str(root / "cache"),
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
    )
    persisted = await store.persist(
        MediaAsset(
            asset_id="live-minio-final",
            kind=AssetKind.FINAL_VIDEO,
            uri=str(source),
            provider="ffmpeg",
        ),
        job_id="live-minio-recovery",
        category="final",
    )

    durable_uri = str(persisted.metadata["durable_uri"])
    source.unlink()
    if source.exists():
        raise RuntimeError("local source artifact was not deleted")

    recovered = await store.materialize(persisted)
    recovered_path = Path(recovered.uri)
    recovered_hash = hashlib.sha256(recovered_path.read_bytes()).hexdigest()
    if source_hash != recovered_hash:
        raise RuntimeError("MinIO recovered artifact SHA256 mismatch")

    probe = await ffprobe(recovered_path)
    stream_types = {stream.get("codec_type") for stream in probe.get("streams") or []}
    if not {"video", "audio"}.issubset(stream_types):
        raise RuntimeError(
            f"recovered artifact missing audio/video stream: {stream_types}"
        )

    report = {
        "passed": True,
        "durable_uri": durable_uri,
        "source_sha256": source_hash,
        "recovered_sha256": recovered_hash,
        "recovered_path": str(recovered_path),
        "stream_types": sorted(stream_types),
        "duration": (probe.get("format") or {}).get("duration"),
    }
    report_path = root / "minio_recovery_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
