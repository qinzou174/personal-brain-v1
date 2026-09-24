"""Encrypted, bounded, ordered offline write queue."""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from personal_brain_domain.common.errors import BrainError
from personal_brain_domain.security.secret_filter import detect_secret

_MAX_QUEUE = 1_000
_MAX_BYTES = 100 * 1024 * 1024


def pending_write_state(*, revoked: bool, queued: bool) -> str:
    if revoked:
        return "stopped"
    return "queued" if queued else "pending"


@dataclass(frozen=True)
class PendingOperation:
    sequence: int
    operation: str
    idempotency_key: str
    payload: dict
    created_at: str
    state: str


class PendingStore:
    """SQLite metadata with AES-256-GCM payloads; key material is caller-owned."""

    def __init__(self, path: str | Path, *, encryption_key: bytes,
                 max_entries: int = _MAX_QUEUE, max_bytes: int = _MAX_BYTES) -> None:
        if not 1 <= max_entries <= _MAX_QUEUE:
            raise ValueError("offline queue entries exceed documented bound")
        if not 1 <= max_bytes <= _MAX_BYTES:
            raise ValueError("offline queue bytes exceed documented bound")
        if len(encryption_key) != 32:
            raise ValueError("offline queue encryption key must be exactly 32 bytes")
        self.path = Path(path).resolve()
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self._cipher = AESGCM(encryption_key)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt":
            os.chmod(self.path.parent, 0o700)
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS pending_operations (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    nonce BLOB NOT NULL,
                    ciphertext BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('queued','conflict')),
                    conflict_code TEXT
                )
            """)
        if os.name != "nt":
            os.chmod(self.path, 0o600)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def enqueue(self, *, operation: str, payload: dict, idempotency_key: UUID | str) -> PendingOperation:
        key = str(idempotency_key)
        try:
            UUID(key)
        except ValueError as error:
            raise BrainError("VALIDATION_FAILED") from error
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        detection = detect_secret(filename="offline-operation.json", content_type="application/json",
                                  content=encoded.decode("utf-8"))
        if detection.matched:
            raise BrainError("SECRET_REJECTED")
        nonce = os.urandom(12)
        ciphertext = self._cipher.encrypt(nonce, encoded, key.encode("ascii"))
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM pending_operations WHERE idempotency_key = ?", (key,),
            ).fetchone()
            if existing is not None:
                connection.commit()
                return self._decode(existing)
            count, used = connection.execute(
                "SELECT count(*), coalesce(sum(length(ciphertext) + length(nonce)), 0) FROM pending_operations",
            ).fetchone()
            if int(count) >= self.max_entries or int(used) + len(ciphertext) + len(nonce) > self.max_bytes:
                connection.rollback()
                raise BrainError("PAYLOAD_TOO_LARGE")
            cursor = connection.execute(
                "INSERT INTO pending_operations(operation,idempotency_key,nonce,ciphertext,created_at,state) "
                "VALUES (?,?,?,?,?,'queued')",
                (operation, key, nonce, ciphertext, created_at),
            )
            sequence = int(cursor.lastrowid)
            connection.commit()
        return PendingOperation(sequence, operation, key, dict(payload), created_at, "queued")

    def list_pending(self, *, limit: int = 100) -> list[PendingOperation]:
        if not 1 <= limit <= _MAX_QUEUE:
            raise ValueError("limit out of bounds")
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM pending_operations ORDER BY sequence LIMIT ?", (limit,),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def replay(
        self, *, send: Callable[[PendingOperation], str],
        authority_check: Callable[[], bool], limit: int = 100,
    ) -> dict[str, int | str]:
        """Replay in insertion order, stopping on revocation, conflict or uncertainty."""
        completed = 0
        for operation in self.list_pending(limit=limit):
            if operation.state == "conflict":
                return {"status": "conflict", "completed": completed}
            if not authority_check():
                return {"status": "stopped", "completed": completed}
            outcome = send(operation)
            if outcome in {"completed", "replayed"}:
                with self._connect() as connection:
                    connection.execute("DELETE FROM pending_operations WHERE sequence = ?", (operation.sequence,))
                completed += 1
                continue
            if outcome == "conflict":
                with self._connect() as connection:
                    connection.execute(
                        "UPDATE pending_operations SET state='conflict', conflict_code='IDEMPOTENCY_CONFLICT' "
                        "WHERE sequence = ?", (operation.sequence,),
                    )
                return {"status": "conflict", "completed": completed}
            return {"status": "pending_sync", "completed": completed}
        return {"status": "completed", "completed": completed}

    def _decode(self, row: sqlite3.Row) -> PendingOperation:
        try:
            plaintext = self._cipher.decrypt(
                bytes(row["nonce"]), bytes(row["ciphertext"]), row["idempotency_key"].encode("ascii"),
            )
            payload = json.loads(plaintext)
        except Exception as error:
            raise BrainError("BRAIN_UNAVAILABLE") from error
        return PendingOperation(
            sequence=int(row["sequence"]), operation=row["operation"],
            idempotency_key=row["idempotency_key"], payload=payload,
            created_at=row["created_at"], state=row["state"],
        )
