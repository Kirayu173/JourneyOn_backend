from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import BinaryIO, Optional
from uuid import uuid4

from app.core.config import settings


logger = logging.getLogger(__name__)


class StorageError(RuntimeError):
    """Raised when file storage operations fail."""


class FileStorage:
    """Abstract storage backend interface."""

    def save_file(
        self,
        file_obj: BinaryIO,
        *,
        filename: str | None = None,
        directory: str | None = None,
    ) -> str:
        raise NotImplementedError

    def open_file(self, storage_key: str) -> BinaryIO:
        raise NotImplementedError

    def delete_file(self, storage_key: str) -> None:
        raise NotImplementedError

    def resolve_path(self, storage_key: str) -> Path:
        raise NotImplementedError


class LocalFileStorage(FileStorage):
    """Local filesystem storage backend for development/test."""

    def __init__(self, base_path: str | Path) -> None:
        self.base_path = Path(base_path).expanduser().resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _normalize_directory(self, directory: str | None) -> Path:
        if not directory:
            return Path()
        candidate = Path(directory.strip("/"))
        if candidate.is_absolute() or ".." in candidate.parts:
            raise StorageError("invalid_directory")
        return candidate

    def _build_storage_key(self, *, directory: Path, filename: str | None) -> str:
        suffix = Path(filename).suffix if filename else ""
        key_name = f"{uuid4().hex}{suffix}"
        full_path = directory / key_name if directory else Path(key_name)
        return full_path.as_posix()

    def save_file(
        self,
        file_obj: BinaryIO,
        *,
        filename: str | None = None,
        directory: str | None = None,
    ) -> str:
        file_obj.seek(0)
        subdir = self._normalize_directory(directory)
        storage_key = self._build_storage_key(directory=subdir, filename=filename)
        target_path = self.base_path / storage_key
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(target_path, "wb") as target:
                shutil.copyfileobj(file_obj, target)
        except OSError as exc:
            logger.exception("Failed to store file", exc_info=exc)
            raise StorageError("write_failed") from exc
        return storage_key

    def open_file(self, storage_key: str) -> BinaryIO:
        path = self.resolve_path(storage_key)
        try:
            return open(path, "rb")
        except OSError as exc:
            raise StorageError("file_not_found") from exc

    def delete_file(self, storage_key: str) -> None:
        path = self.resolve_path(storage_key)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Failed to delete file %s", storage_key, exc_info=exc)

    def resolve_path(self, storage_key: str) -> Path:
        normalized = Path(storage_key)
        if normalized.is_absolute() or ".." in normalized.parts:
            raise StorageError("invalid_storage_key")
        return self.base_path / normalized


_storage_instance: Optional[FileStorage] = None


def get_storage() -> FileStorage:
    """Return configured storage backend instance (singleton)."""

    global _storage_instance
    if _storage_instance is not None:
        return _storage_instance

    backend = (settings.STORAGE_BACKEND or "local").lower()
    if backend == "local":
        base_dir = settings.LOCAL_STORAGE_PATH or os.getcwd()
        _storage_instance = LocalFileStorage(base_dir)
    else:
        raise StorageError(f"unsupported_backend:{backend}")
    return _storage_instance


__all__ = ["FileStorage", "LocalFileStorage", "StorageError", "get_storage"]
