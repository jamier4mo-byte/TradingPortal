"""Blob storage behind one interface: LocalStorage under the data dir, or S3Storage (Tigris) in production.

Keys are relative, slash-separated and path-safe. Nothing here is served as public static files.
The backend is chosen by STORAGE_BACKEND (local | s3). With `s3`, the bucket, endpoint and region come
from the names `fly storage create` sets (BUCKET_NAME, AWS_ENDPOINT_URL_S3, AWS_REGION) and the access
keys from the standard AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY, which boto3 reads on its own.

Both backends raise FileNotFoundError from `get()` for a missing key, so callers behave the same way.
"""

import re
import shutil
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path

from ..core.settings import get_settings

SAFE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9][A-Za-z0-9._-]*)*$")


class StorageError(Exception):
    pass


def check_key(key: str) -> str:
    if not SAFE_KEY.match(key) or ".." in key.split("/"):
        raise StorageError(f"Unsafe storage key: {key!r}")
    return key


class Storage(ABC):
    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    @abstractmethod
    def get(self, key: str) -> bytes:
        """The object's bytes. Raises FileNotFoundError when the key doesn't exist."""

    @abstractmethod
    def path(self, key: str) -> Path | None:
        """A local path when the backend has one (lets FastAPI stream it); None for remote stores."""

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...


class LocalStorage(Storage):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        check_key(key)
        target = (self.root / key).resolve()
        if self.root not in target.parents:
            raise StorageError("Key escapes the storage root.")
        return target

    def put(self, key: str, data: bytes, content_type: str) -> None:
        target = self._resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(target)

    def get(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def path(self, key: str) -> Path | None:
        p = self._resolve(key)
        return p if p.is_file() else None

    def delete(self, key: str) -> None:
        p = self._resolve(key)
        if p.is_file():
            p.unlink()

    def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()

    def wipe(self) -> None:  # tests only
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir(parents=True, exist_ok=True)


class S3Storage(Storage):
    """Screenshots in an S3-compatible bucket (Tigris on Fly). Every key sits under `prefix`.

    The boto3 client is made on first use, so tests can build the store inside moto's `mock_aws()`.
    Tigris wants virtual-hosted addressing (bucket.host), which is also what AWS uses, so it's fixed here.
    """

    def __init__(
        self,
        bucket: str,
        *,
        prefix: str = "screenshots/",
        endpoint_url: str | None = None,
        region: str = "auto",
        client=None,
    ) -> None:
        if not bucket:
            raise StorageError("S3 storage needs a bucket name (BUCKET_NAME).")
        self.bucket = bucket
        clean = prefix.strip("/")
        self.prefix = f"{clean}/" if clean else ""
        self.endpoint_url = endpoint_url or None
        self.region = region or "auto"
        self._client = client

    @property
    def client(self):
        if self._client is None:
            import boto3
            from botocore.config import Config

            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                region_name=self.region,
                config=Config(
                    s3={"addressing_style": "virtual"},
                    retries={"max_attempts": 3, "mode": "standard"},
                    connect_timeout=10,
                    read_timeout=30,
                ),
            )
        return self._client

    def object_key(self, key: str) -> str:
        return self.prefix + check_key(key)

    @staticmethod
    def _is_missing(exc: Exception) -> bool:
        code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
        status = getattr(exc, "response", {}).get("ResponseMetadata", {}).get("HTTPStatusCode")
        return code in ("NoSuchKey", "404", "NotFound") or status == 404

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket, Key=self.object_key(key), Body=data, ContentType=content_type
        )

    def get(self, key: str) -> bytes:
        from botocore.exceptions import ClientError

        try:
            res = self.client.get_object(Bucket=self.bucket, Key=self.object_key(key))
        except ClientError as exc:
            if self._is_missing(exc):
                raise FileNotFoundError(key) from exc
            raise
        return res["Body"].read()

    def path(self, key: str) -> Path | None:
        check_key(key)
        return None

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self.object_key(key))

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=self.object_key(key))
        except ClientError as exc:
            if self._is_missing(exc):
                return False
            raise
        return True


def local_storage() -> LocalStorage:
    """The data-dir store, whichever backend is configured (used by `migrate-screenshots`)."""
    return LocalStorage(get_settings().resolved_data_dir / "screenshots")


@lru_cache
def get_storage() -> Storage:
    s = get_settings()
    if s.storage_backend == "s3":
        if not s.s3_bucket:  # Settings already refuses this; belt and braces for direct construction
            raise RuntimeError(
                "STORAGE_BACKEND=s3 but BUCKET_NAME is not set. Run `fly storage create` (Tigris) or set "
                "STORAGE_BACKEND=local."
            )
        return S3Storage(s.s3_bucket, prefix=s.s3_prefix, endpoint_url=s.s3_endpoint_url, region=s.s3_region)
    return local_storage()
