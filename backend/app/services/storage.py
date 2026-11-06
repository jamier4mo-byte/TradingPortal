"""Blob storage behind one interface. LocalStorage under the data dir now; S3/Tigris in Prompt 5.

Keys are relative, slash-separated and path-safe. Nothing here is served as public static files.
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
    def get(self, key: str) -> bytes: ...

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


@lru_cache
def get_storage() -> Storage:
    return LocalStorage(get_settings().resolved_data_dir / "screenshots")
