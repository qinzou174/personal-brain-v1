"""Durable idempotency claims with replay, conflict and tombstone semantics.

ER-07: ``(client_id, operation, idempotency_key)`` is unique. A claim records the
payload digest so a late retry with identical content replays the stored outcome,
different content raises ``IDEMPOTENCY_CONFLICT``, and a deletion tombstone keeps
only the irreversible request key (never the body digest) so a late retry cannot
recreate deleted content.
"""

from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy import String, Uuid, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.selectable import FromClause

from personal_brain_domain.common.errors import BrainError


DELETED_OUTCOME = {"status": "deleted", "persistence": "tombstone"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _db_value(table: FromClause, column: str, value: Any) -> Any:
    """Adapt UUIDs to reflected native UUID or portable textual columns."""
    if not isinstance(value, uuid.UUID):
        return value
    kind = table.c[column].type
    if isinstance(kind, Uuid) and kind.as_uuid:
        return value
    if isinstance(kind, String) and kind.length == 32:
        return value.hex
    return str(value)


def resolve_replay(
    stored_digest: str | None,
    incoming_digest: str,
    *,
    existing_outcome: Mapping[str, Any] | None,
    tombstoned: bool = False,
) -> dict[str, Any]:
    """Never recreate content from a late retry against a deletion tombstone.

    Tombstones intentionally lack a content digest: retaining one after deletion
    would expose guesses about a private request body.
    """
    if tombstoned:
        if stored_digest is not None:
            raise BrainError("INTERNAL_SAFE_ERROR")
        return dict(DELETED_OUTCOME)
    if not stored_digest or not hmac.compare_digest(stored_digest, incoming_digest):
        raise BrainError("IDEMPOTENCY_CONFLICT")
    if existing_outcome is None:
        raise BrainError("BRAIN_UNAVAILABLE")
    return dict(existing_outcome)


@dataclass(frozen=True)
class Claim:
    """Result of a durable claim attempt.

    ``state`` is one of:
    - ``created``: this caller won the unique ``(client_id, operation, key)`` claim;
    - ``replay``: a completed claim with the same digest returned its stored outcome;
    - ``in_progress``: a live claim with the same digest is still being processed;
    - ``deleted``: the request key is tombstoned; deleted content is never recreated.
    """

    id: str | uuid.UUID
    state: str
    outcome: Mapping[str, Any] | None = None


def claim_request(
    session: Any,
    table: FromClause,
    *,
    owner_id: str | uuid.UUID,
    client_id: str | uuid.UUID,
    operation: str,
    idempotency_key: str | uuid.UUID,
    payload_digest: str,
) -> Claim:
    """Atomically claim a request key or resolve the existing claim.

    Insertion first wins; a concurrent duplicate hits the unique constraint, is
    rolled back to a savepoint, and falls through to deterministic replay,
    in-progress, or tombstone resolution against the existing row.
    """
    # Reflected PostgreSQL UUID columns require ``uuid.UUID`` while the small
    # portable test tables used by adapters may deliberately use text ids.
    claim_id: str | uuid.UUID = _db_value(table, "id", uuid.uuid4())
    owner_id = _db_value(table, "owner_id", owner_id)
    client_id = _db_value(table, "client_id", client_id)
    idempotency_key = _db_value(table, "idempotency_key", idempotency_key)
    values = dict(
        id=claim_id,
        owner_id=owner_id,
        client_id=client_id,
        operation=operation,
        idempotency_key=idempotency_key,
        payload_digest=payload_digest,
        outcome=None,
        status="claimed",
    )
    # SQLite's legacy driver may commit a released savepoint when no physical
    # outer BEGIN has been emitted.  The portable adapter therefore uses a
    # select-first path; PostgreSQL retains insert-first conflict arbitration.
    if session.get_bind().dialect.name == "sqlite":
        existing = session.execute(
            select(table.c.id).where(
                table.c.client_id == client_id,
                table.c.operation == operation,
                table.c.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing is None:
            session.execute(table.insert().values(**values))
            return Claim(id=claim_id, state="created")
    else:
        try:
            with session.begin_nested():
                session.execute(table.insert().values(**values))
        except IntegrityError:
            pass
        else:
            return Claim(id=claim_id, state="created")

    row = session.execute(
        select(table).where(
            table.c.client_id == client_id,
            table.c.operation == operation,
            table.c.idempotency_key == idempotency_key,
        )
    ).mappings().one()

    if row["status"] == "tombstoned":
        return Claim(id=row["id"], state="deleted")
    if not hmac.compare_digest(row["payload_digest"], payload_digest):
        raise BrainError("IDEMPOTENCY_CONFLICT")
    if row["status"] == "completed":
        return Claim(id=row["id"], state="replay", outcome=row["outcome"])
    return Claim(id=row["id"], state="in_progress")


def complete_claim(
    session: Any,
    table: FromClause,
    *,
    claim_id: str | uuid.UUID,
    outcome: Mapping[str, Any],
) -> None:
    """Attach the authoritative outcome to a claimed request key.

    Completing an already-completed claim is idempotent for the identical outcome
    and conflicts otherwise; a tombstoned claim can never be completed.
    """
    row = session.execute(select(table).where(table.c.id == claim_id)).mappings().one_or_none()
    if row is None:
        raise BrainError("NOT_FOUND")
    if row["status"] == "completed":
        if row["outcome"] != outcome:
            raise BrainError("IDEMPOTENCY_CONFLICT")
        return
    if row["status"] == "tombstoned":
        raise BrainError("INTERNAL_SAFE_ERROR")
    session.execute(
        table.update()
        .where(table.c.id == claim_id, table.c.status == "claimed")
        .values(status="completed", outcome=outcome)
    )


def tombstone_claim(
    session: Any,
    table: FromClause,
    *,
    claim_id: str | uuid.UUID,
) -> None:
    """Erase the body digest and outcome, keeping only the request key.

    The resulting row satisfies ``status == 'tombstoned'`` with a NULL digest, so
    a late retry resolves to ``deleted`` instead of recreating removed content.
    """
    row = session.execute(select(table).where(table.c.id == claim_id)).mappings().one_or_none()
    if row is None:
        raise BrainError("NOT_FOUND")
    if row["status"] == "tombstoned":
        return
    values: dict[str, Any] = {"status": "tombstoned", "outcome": None, "payload_digest": None}
    if "tombstoned_at" in table.c:
        values["tombstoned_at"] = _utcnow()
    session.execute(table.update().where(table.c.id == claim_id).values(**values))
