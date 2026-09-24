"""Repository-enforced owner, scope and sensitivity predicates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping, Sequence

from sqlalchemy import Table, case, select
from sqlalchemy.orm import Session

from personal_brain_domain.common.errors import BrainError
from personal_brain_domain.security.policy import authorize


_RANK = {"normal": 0, "personal": 1, "private": 2, "highly_private": 3}


@dataclass(frozen=True, slots=True)
class ScopedPredicate:
    owner_id: str
    scope: str
    max_sensitivity: str

    def __post_init__(self) -> None:
        if not self.owner_id or not self.scope or self.max_sensitivity not in _RANK:
            raise BrainError("AUTH_INVALID")


class ScopedRepository:
    """SQL adapter; protected tables must expose id/owner_id/scope/sensitivity."""

    def __init__(self, session: Session, table: Table) -> None:
        needed = {"id", "owner_id", "scope", "sensitivity"}
        if not needed <= set(table.c.keys()):
            raise ValueError("protected table lacks mandatory scope columns")
        self.session = session
        self.table = table

    def read_by_id(self, record_id: str, predicate: ScopedPredicate) -> dict | None:
        sensitivity_rank = case(
            *((self.table.c.sensitivity == name, rank) for name, rank in _RANK.items()),
            else_=99,
        )
        statement = select(self.table).where(
            self.table.c.id == record_id,
            self.table.c.owner_id == predicate.owner_id,
            self.table.c.scope == predicate.scope,
            sensitivity_rank <= _RANK[predicate.max_sensitivity],
        )
        row = self.session.execute(statement).mappings().first()
        return dict(row) if row is not None else None


def authorized_read(
    client: Mapping[str, object],
    grants: Sequence[Mapping[str, object]],
    tool: str,
    scope: str,
    sensitivity: str,
    repository: ScopedRepository,
    record_id: str,
    *,
    now: datetime | None = None,
    parent_project_scope: str | None = None,
) -> dict:
    """Never give a protected identifier to the repository before authorization."""
    authorize(client, grants, tool, scope, sensitivity, now=now or datetime.now(timezone.utc),
              parent_project_scope=parent_project_scope)
    owner_id = client.get("owner_id")
    if not isinstance(owner_id, str) or not owner_id:
        raise BrainError("AUTH_INVALID")
    predicate = ScopedPredicate(owner_id=owner_id, scope=scope, max_sensitivity=sensitivity)
    result = repository.read_by_id(record_id, predicate)
    if result is None:
        raise BrainError("NOT_FOUND")
    return result
