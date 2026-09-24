"""Storage backend contract and content-addressed atomic promotion.

FR-032/FR-033/FR-040: a backend promotes bytes to a content-addressed key only
after hash/size verification; domain identity never depends on storage path.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import BinaryIO


@dataclass(frozen=True)
class StoredObject:
    storage_key: str
    sha256: str
    size_bytes: int


class StorageBackend(ABC):
    @abstractmethod
    def store_atomic(self, stream: BinaryIO, *, expected_sha256: str, expected_size: int,
                     content_type: str) -> StoredObject:
        """Verify hash/size then atomically promote; caller never selects the path."""
        raise NotImplementedError

    @abstractmethod
    def read(self, storage_key: str) -> bytes:
        raise NotImplementedError