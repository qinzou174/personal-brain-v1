"""Protected data never leaves SQL before owner/scope/sensitivity filtering."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import Column, MetaData, String, Table, create_engine
from sqlalchemy.orm import Session

from personal_brain_domain.common.errors import BrainError
from personal_brain_infra.persistence.scoped_repository import ScopedRepository, authorized_read


CLIENT = {
    "client_id": "client-a", "owner_id": "owner-a", "status": "active",
    "permission_epoch": 1, "authenticated_epoch": 1,
    "allowed_tools": ["get_note"], "allowed_scopes": ["personal"],
}
GRANT = {"client_id": "client-a", "effect": "allow", "tool_pattern": "get_note", "scope_pattern": "personal",
         "sensitivity_ceiling": "personal"}
NOW = datetime(2026, 9, 23, tzinfo=timezone.utc)


def test_sql_enforces_owner_scope_and_sensitivity():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    notes = Table("notes", metadata, Column("id", String, primary_key=True),
                  Column("owner_id", String), Column("scope", String),
                  Column("sensitivity", String), Column("body", String))
    metadata.create_all(engine)
    with Session(engine) as session:
        session.execute(notes.insert(), [
            {"id": "ok", "owner_id": "owner-a", "scope": "personal", "sensitivity": "personal", "body": "one"},
            {"id": "other", "owner_id": "owner-b", "scope": "personal", "sensitivity": "normal", "body": "two"},
            {"id": "wrong-scope", "owner_id": "owner-a", "scope": "diary", "sensitivity": "normal", "body": "three"},
            {"id": "too-private", "owner_id": "owner-a", "scope": "personal", "sensitivity": "private", "body": "four"},
        ])
        session.commit()
        repository = ScopedRepository(session, notes)
        assert authorized_read(CLIENT, [GRANT], "get_note", "personal", "personal", repository, "ok", now=NOW)["body"] == "one"
        for record_id in ("other", "wrong-scope", "too-private"):
            with pytest.raises(BrainError) as caught:
                authorized_read(CLIENT, [GRANT], "get_note", "personal", "personal", repository, record_id, now=NOW)
            assert caught.value.code == "NOT_FOUND"
    engine.dispose()
