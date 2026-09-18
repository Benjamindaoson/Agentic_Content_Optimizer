"""Durable artifact storage for multimodal production media."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Optional, Protocol

from minio import Minio

from .multimodal_content_workflow import MediaAsset


class ArtifactStore(Protocol):
    async def persist(
        self,
        asset: MediaAsset,
        *,
        job_id: str,
        category: str,
    ) -> MediaAsset:
        """Persist a local artifact and return an asset with durable metadata."""

    async def materialize(self, asset: MediaAsset) -> MediaAsset:
        """Ensure a durable artifact is available on the local filesystem."""


class MinIOArtifactStore:
    """MinIO/S3-compatible artifact store with local materialization cache."""

    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        cache_dir: str,
        secure: bool = False,
        client: Optional[Any] = None,
    ) -> None:
        if not endpoint:
            raise ValueError("MinIO endpoint is required")
        if not access_key or not secret_key:
            raise ValueError("MinIO credentials are required")
        if not bucket:
            raise ValueError("MinIO bucket is required")

        self.bucket = bucket
        self.cache_dir = Path(cache_dir)
        self.client = client or Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self._bucket_ready = False
        self._bucket_lock = asyncio.Lock()

    async def persist(
        self,
        asset: MediaAsset,
        *,
        job_id: str,
        category: str,
    ) -> MediaAsset:
        source = self._local_path(asset.uri)
        if not source.exists():
            raise FileNotFoundError(source)

        await self._ensure_bucket()

        object_name = (
            f"{self._safe(job_id)}/{self._safe(category)}/{self._safe(source.name)}"
        )
        await asyncio.to_thread(
            self.client.fput_object,
            self.bucket,
            object_name,
            str(source),
        )

        metadata = dict(asset.metadata)
        metadata.update(
            {
                "durable_uri": f"s3://{self.bucket}/{object_name}",
                "artifact_bucket": self.bucket,
                "artifact_object": object_name,
            }
        )
        return MediaAsset(
            asset_id=asset.asset_id,
            kind=asset.kind,
            uri=asset.uri,
            provider=asset.provider,
            metadata=metadata,
        )

    async def materialize(self, asset: MediaAsset) -> MediaAsset:
        try:
            local = self._local_path(asset.uri)
            if local.exists():
                return asset
        except ValueError:
            local = None

        bucket, object_name = self._durable_location(asset)
        target = self.cache_dir / bucket / object_name
        target.parent.mkdir(parents=True, exist_ok=True)

        if not target.exists():
            await self._ensure_bucket()
            await asyncio.to_thread(
                self.client.fget_object,
                bucket,
                object_name,
                str(target),
            )

        metadata = dict(asset.metadata)
        metadata["materialized_from"] = f"s3://{bucket}/{object_name}"
        return MediaAsset(
            asset_id=asset.asset_id,
            kind=asset.kind,
            uri=str(target),
            provider=asset.provider,
            metadata=metadata,
        )

    async def _ensure_bucket(self) -> None:
        if self._bucket_ready:
            return
        async with self._bucket_lock:
            if self._bucket_ready:
                return
            exists = await asyncio.to_thread(
                self.client.bucket_exists,
                self.bucket,
            )
            if not exists:
                await asyncio.to_thread(self.client.make_bucket, self.bucket)
            self._bucket_ready = True

    def _durable_location(self, asset: MediaAsset) -> tuple[str, str]:
        durable_uri = str(asset.metadata.get("durable_uri") or "")
        if not durable_uri and asset.uri.startswith("s3://"):
            durable_uri = asset.uri
        if not durable_uri.startswith("s3://"):
            raise ValueError(
                f"asset has no durable MinIO/S3 location: {asset.asset_id}"
            )

        without_scheme = durable_uri[5:]
        bucket, sep, object_name = without_scheme.partition("/")
        if not sep or not bucket or not object_name:
            raise ValueError(f"invalid durable artifact URI: {durable_uri}")
        return bucket, object_name

    @staticmethod
    def _local_path(uri: str) -> Path:
        if uri.startswith("file://"):
            return Path(uri[7:])
        if "://" in uri:
            raise ValueError(f"not a local artifact URI: {uri}")
        return Path(uri)

    @staticmethod
    def _safe(value: str) -> str:
        return "".join(
            char if char.isalnum() or char in "-_." else "_" for char in value
        )
