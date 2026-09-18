"""Real platform publishers and metrics collectors for multimodal output."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from .multimodal_artifacts import ArtifactStore
from .multimodal_content_workflow import ProductionState


class TikTokContentPublisher:
    """TikTok Content Posting API direct-post implementation.

    Publishing is intentionally invoked only after the production job has
    passed evaluation and explicit human approval.
    """

    def __init__(
        self,
        *,
        access_token: str,
        api_base: str = "https://open.tiktokapis.com",
        privacy_level: str = "SELF_ONLY",
        request_timeout_seconds: float = 120.0,
        artifact_store: Optional[ArtifactStore] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        if not access_token:
            raise ValueError("TikTok access token is required")
        self.access_token = access_token
        self.api_base = api_base.rstrip("/")
        self.privacy_level = privacy_level
        self.request_timeout_seconds = request_timeout_seconds
        self.artifact_store = artifact_store
        self._client = client

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

    async def publish(self, state: ProductionState) -> Dict[str, Any]:
        if state.platform.lower() != "tiktok":
            raise ValueError("TikTok publisher only accepts platform=tiktok")
        if state.final_video is None:
            raise ValueError("final video is required before publishing")
        if state.quality_report is None or not state.quality_report.passed:
            raise ValueError("job must pass the quality gate before publishing")
        if not state.approved:
            raise ValueError("explicit human approval is required before publishing")

        asset = state.final_video
        if self.artifact_store is not None:
            asset = await self.artifact_store.materialize(asset)

        video_path = self._local_path(asset.uri)
        if not video_path.exists():
            raise FileNotFoundError(video_path)

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=self.request_timeout_seconds
        )
        try:
            creator = await self.query_creator_info(client=client)
            privacy_options = list(creator.get("privacy_level_options") or [])
            if self.privacy_level not in privacy_options:
                raise ValueError(
                    "configured TikTok privacy level is not currently allowed "
                    f"for this creator: {self.privacy_level}"
                )

            title = self._caption(state)
            source_info = self._file_source_info(video_path)
            response = await client.post(
                f"{self.api_base}/v2/post/publish/video/init/",
                headers=self.headers,
                json={
                    "post_info": {
                        "title": title,
                        "privacy_level": self.privacy_level,
                        "disable_duet": False,
                        "disable_comment": False,
                        "disable_stitch": False,
                        "video_cover_timestamp_ms": 1000,
                        "brand_organic_toggle": False,
                        "is_aigc": True,
                    },
                    "source_info": source_info,
                },
            )
            payload = self._checked_json(response)
            data = dict(payload.get("data") or {})
            publish_id = str(data["publish_id"])
            upload_url = str(data["upload_url"])

            await self._upload_file(
                client,
                upload_url=upload_url,
                video_path=video_path,
                chunk_size=int(source_info["chunk_size"]),
                total_chunk_count=int(source_info["total_chunk_count"]),
            )
            status = await self.fetch_publish_status(
                publish_id,
                client=client,
            )
            return {
                "platform": "tiktok",
                "publish_id": publish_id,
                "status": status.get("status"),
                "status_detail": status,
                "is_aigc": True,
                "privacy_level": self.privacy_level,
            }
        finally:
            if owns_client:
                await client.aclose()

    async def query_creator_info(
        self,
        *,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Dict[str, Any]:
        owns_client = client is None
        resolved_client = client or httpx.AsyncClient(
            timeout=self.request_timeout_seconds
        )
        try:
            response = await resolved_client.post(
                f"{self.api_base}/v2/post/publish/creator_info/query/",
                headers=self.headers,
                json={},
            )
            payload = self._checked_json(response)
            return dict(payload.get("data") or {})
        finally:
            if owns_client:
                await resolved_client.aclose()

    async def fetch_publish_status(
        self,
        publish_id: str,
        *,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Dict[str, Any]:
        owns_client = client is None
        resolved_client = client or httpx.AsyncClient(
            timeout=self.request_timeout_seconds
        )
        try:
            response = await resolved_client.post(
                f"{self.api_base}/v2/post/publish/status/fetch/",
                headers=self.headers,
                json={"publish_id": publish_id},
            )
            payload = self._checked_json(response)
            return dict(payload.get("data") or {})
        finally:
            if owns_client:
                await resolved_client.aclose()

    async def query_video_metrics(
        self,
        video_id: str,
        *,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Dict[str, Any]:
        """Fetch public video engagement metrics using TikTok Display API."""

        owns_client = client is None
        resolved_client = client or httpx.AsyncClient(
            timeout=self.request_timeout_seconds
        )
        try:
            response = await resolved_client.post(
                (
                    f"{self.api_base}/v2/video/query/"
                    "?fields=id,like_count,comment_count,share_count,"
                    "view_count,is_aigc"
                ),
                headers=self.headers,
                json={"filters": {"video_ids": [video_id]}},
            )
            payload = self._checked_json(response)
            videos = list((payload.get("data") or {}).get("videos") or [])
            if not videos:
                raise RuntimeError(f"TikTok video not found: {video_id}")
            return dict(videos[0])
        finally:
            if owns_client:
                await resolved_client.aclose()

    async def _upload_file(
        self,
        client: httpx.AsyncClient,
        *,
        upload_url: str,
        video_path: Path,
        chunk_size: int,
        total_chunk_count: int,
    ) -> None:
        total_size = video_path.stat().st_size
        with video_path.open("rb") as handle:
            start = 0
            for index in range(total_chunk_count):
                if index == total_chunk_count - 1:
                    length = total_size - start
                else:
                    length = chunk_size
                chunk = handle.read(length)
                if len(chunk) != length:
                    raise IOError("unexpected EOF while reading TikTok upload chunk")
                end = start + length - 1
                response = await client.put(
                    upload_url,
                    headers={
                        "Content-Type": "video/mp4",
                        "Content-Length": str(length),
                        "Content-Range": f"bytes {start}-{end}/{total_size}",
                    },
                    content=chunk,
                )
                response.raise_for_status()
                start = end + 1

        if start != total_size:
            raise RuntimeError(
                f"TikTok upload incomplete: uploaded={start}, total={total_size}"
            )

    @staticmethod
    def _file_source_info(video_path: Path) -> Dict[str, Any]:
        size = video_path.stat().st_size
        if size <= 0:
            raise ValueError("video file is empty")

        max_chunk = 64 * 1024 * 1024
        min_chunk = 5 * 1024 * 1024
        if size <= max_chunk:
            chunk_size = size
            total_chunk_count = 1
        else:
            chunk_size = max_chunk
            total_chunk_count = max(1, math.floor(size / chunk_size))
            final_size = size - chunk_size * (total_chunk_count - 1)
            if final_size > 128 * 1024 * 1024:
                total_chunk_count += 1
                final_size = size - chunk_size * (total_chunk_count - 1)
            if total_chunk_count > 1 and chunk_size < min_chunk:
                raise ValueError("TikTok chunk size would be below 5 MB")
            if final_size > 128 * 1024 * 1024:
                raise ValueError("TikTok final upload chunk would exceed 128 MB")

        return {
            "source": "FILE_UPLOAD",
            "video_size": size,
            "chunk_size": chunk_size,
            "total_chunk_count": total_chunk_count,
        }

    @staticmethod
    def _caption(state: ProductionState) -> str:
        title = str(state.script.get("title") or state.script.get("hook") or "")
        body = str(state.script.get("cta") or "")
        caption = f"{title} {body}".strip()
        return caption[:2200]

    @staticmethod
    def _checked_json(response: httpx.Response) -> Dict[str, Any]:
        response.raise_for_status()
        payload = response.json()
        error = payload.get("error") or {}
        code = error.get("code")
        if code not in (None, 0, "0", "ok"):
            raise RuntimeError(
                "TikTok API error "
                f"{code}: {error.get('message') or 'unknown error'}"
            )
        return payload

    @staticmethod
    def _local_path(uri: str) -> Path:
        if uri.startswith("file://"):
            return Path(uri[7:])
        if "://" in uri:
            raise ValueError(f"TikTok FILE_UPLOAD requires a local artifact: {uri}")
        return Path(uri)
