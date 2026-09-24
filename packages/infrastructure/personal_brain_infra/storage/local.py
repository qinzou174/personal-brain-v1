"""Local filesystem storage backend.

FR-032/FR-033/FR-039/FR-040: bytes are stored under a content-derived key after
hash/size verification; the caller never chooses the path. Reuses StoredObject.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import BinaryIO

from personal_brain_infra.storage.base import StorageBackend, StoredObject


class LocalStorage(StorageBackend):
    def __init__(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        self._root = root.resolve()

    def _key(self, sha256: str) -> Path:
        return self._root / sha256[:2] / sha256[2:]

    def store_atomic(self, stream: BinaryIO, *, expected_sha256: str, expected_size: int,
                     content_type: str) -> StoredObject:
        content = stream.read(expected_size + 1)
        if len(content) != expected_size:
            raise ValueError("size mismatch during upload")
        actual = hashlib.sha256(content).hexdigest()
        if actual != expected_sha256:
            raise ValueError("hash mismatch during upload")
        target = self._key(expected_sha256)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.parent / f".tmp-{uuid.uuid4().hex}"
        tmp.write_bytes(content)
        tmp.replace(target)  # atomic promotion
        return StoredObject(storage_key=str(target.relative_to(self._root)), sha256=expected_sha256, size_bytes=expected_size)

    def read(self, storage_key: str) -> bytes:
        target = self._root / storage_key
        if not target.resolve().is_relative_to(self._root):
            raise ValueError("storage key escapes root")
        return target.read_bytes()