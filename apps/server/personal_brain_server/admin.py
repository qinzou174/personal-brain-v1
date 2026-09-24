"""Local operator-only owner/client lifecycle commands.

These helpers are deliberately not exposed through HTTP or MCP.  They require
direct access to the private database DSN and deliver reusable credentials only
to a caller-selected, newly-created private file.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID, uuid4

import sqlalchemy as sa

from personal_brain_domain.common.errors import BrainError
from personal_brain_domain.security.clients import Client, issue_credential


DEFAULT_SCOPES = (
    "knowledge", "finance", "todo", "self", "asset", "review", "operations", "projects",
)
# Scopes that carry retrievable content; search/context reads are granted per scope
# so a client can search exactly the domains it already holds (ER-06 least privilege).
_SEARCHABLE_SCOPES = ("knowledge", "finance", "todo", "self", "asset", "projects")
DEFAULT_TOOLS = (
    "knowledge.write", "knowledge.read", "search.read", "context.read",
    "finance.write", "finance.read",
    "todo.write", "todo.read", "self.write", "self.read", "asset.write",
    "review.write", "review.read", "operation.read", "project.write",
)
_TOOL_SCOPES: dict[str, tuple[str, ...]] = {
    "knowledge.write": ("knowledge",), "knowledge.read": ("knowledge",),
    "search.read": _SEARCHABLE_SCOPES, "context.read": _SEARCHABLE_SCOPES,
    "finance.write": ("finance",), "finance.read": ("finance",),
    "todo.write": ("todo",), "todo.read": ("todo",),
    "self.write": ("self",), "self.read": ("self",), "asset.write": ("asset",),
    "review.write": ("review",), "review.read": ("review",),
    "operation.read": ("operations",), "project.write": ("projects",),
}


def _uuid(value: str | UUID) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(value)
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError("identifier must be a UUID") from error


def write_credential_once(path: str | Path, credential: str) -> Path:
    """Atomically create a credential file without ever overwriting one."""
    target = Path(path)
    if not target.is_absolute() or ".." in target.parts:
        raise ValueError("credential path must be absolute and normalized")
    target.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(target, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(credential)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    if os.name == "posix":
        os.chmod(target, 0o600)
    return target


def _audit(
    session: Any, tables: Mapping[str, sa.Table], *, owner_id: UUID,
    client_id: UUID | None,
    action: str, scope: str, target_category: str, target_id: UUID,
) -> None:
    table = tables.get("audit_events")
    if table is None:
        return
    session.execute(table.insert().values(
        id=uuid4(), owner_id=owner_id, client_id=client_id,
        correlation_id=uuid4(), action=action,
        tool="operator.cli", effective_scope=scope, target_category=target_category,
        target_id=target_id, outcome="completed", error_code=None, duration_ms=0,
        occurred_at=datetime.now(timezone.utc), risk="broad_permission_change",
        authorization_decision="owner_local_operator",
    ))


def provision_client(
    factory: Any, tables: Mapping[str, sa.Table], *, display_name: str,
    client_type: str, credential_file: str | Path,
) -> dict[str, str]:
    if not display_name.strip() or not client_type.strip():
        raise ValueError("client name and type are required")
    owners, clients, credentials, grants = (
        tables["owners"], tables["clients"], tables["credentials"], tables["permission_grants"],
    )
    now = datetime.now(timezone.utc)
    with factory() as session:
        existing_owners = list(session.scalars(sa.select(owners.c.id)))
        if len(existing_owners) > 1:
            raise RuntimeError("single-owner invariant violated")
        owner_id = existing_owners[0] if existing_owners else uuid4()
        duplicate = session.scalar(sa.select(clients.c.id).where(
            clients.c.display_name == display_name.strip(), clients.c.status != "revoked",
        ))
        if duplicate is not None:
            raise ValueError("an active client with this name already exists")

    client_id = uuid4()
    client = Client(
        id=str(client_id), owner_id=str(owner_id), status="active", permission_epoch=1,
        allowed_scopes=frozenset(DEFAULT_SCOPES), allowed_tools=frozenset(DEFAULT_TOOLS),
    )
    token, credential = issue_credential(client, now=now)
    target = write_credential_once(credential_file, token)
    try:
        with factory.begin() as session:
            if not existing_owners:
                session.execute(owners.insert().values(id=owner_id))
            session.execute(clients.insert().values(
                id=client_id, owner_id=owner_id, display_name=display_name.strip(),
                client_type=client_type.strip(), status="active", scopes=list(DEFAULT_SCOPES),
                allowed_tools=list(DEFAULT_TOOLS), permission_epoch=1,
            ))
            session.execute(credentials.insert().values(
                id=_uuid(credential.id), client_id=client_id, verifier=credential.verifier,
                issued_at=credential.issued_at, expires_at=None, revoked_at=None,
                overlap_deadline=None,
            ))
            for tool in DEFAULT_TOOLS:
                for scope in _TOOL_SCOPES[tool]:
                    session.execute(grants.insert().values(
                        id=uuid4(), client_id=client_id, effect="allow",
                        scope_pattern=scope, tool_pattern=tool,
                        sensitivity_ceiling="private", effective_from=now, effective_to=None,
                        issuer="owner_local_operator", reason="initial least-privilege client profile",
                    ))
            _audit(session, tables, owner_id=owner_id, client_id=client_id,
                   action="provision_client",
                   scope="operations", target_category="client", target_id=client_id)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return {"owner_id": str(owner_id), "client_id": str(client_id),
            "credential_file": str(target), "status": "active"}


def rotate_client_credential(
    factory: Any, tables: Mapping[str, sa.Table], *, client_id: str | UUID,
    credential_file: str | Path,
) -> dict[str, str]:
    client_uuid = _uuid(client_id)
    now = datetime.now(timezone.utc)
    with factory() as session:
        row = session.execute(sa.select(tables["clients"]).where(
            tables["clients"].c.id == client_uuid,
        )).mappings().one_or_none()
    if row is None:
        raise BrainError("NOT_FOUND")
    client = Client(
        id=str(row["id"]), owner_id=str(row["owner_id"]), status=row["status"],
        permission_epoch=int(row["permission_epoch"]),
        allowed_scopes=frozenset(row["scopes"]),
        allowed_tools=frozenset(row["allowed_tools"]),
    )
    token, credential = issue_credential(client, now=now)
    target = write_credential_once(credential_file, token)
    try:
        with factory.begin() as session:
            session.execute(tables["credentials"].update().where(
                tables["credentials"].c.client_id == client_uuid,
                tables["credentials"].c.revoked_at.is_(None),
            ).values(revoked_at=now))
            session.execute(tables["credentials"].insert().values(
                id=_uuid(credential.id), client_id=client_uuid, verifier=credential.verifier,
                issued_at=credential.issued_at, expires_at=None, revoked_at=None,
                overlap_deadline=None,
            ))
            _audit(session, tables, owner_id=row["owner_id"], client_id=client_uuid,
                   action="rotate_client_credential",
                   scope="operations", target_category="client", target_id=client_uuid)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return {"client_id": str(client_uuid), "credential_file": str(target), "status": "rotated"}


def revoke_client(
    factory: Any, tables: Mapping[str, sa.Table], *, client_id: str | UUID,
    confirmed_client_id: str | UUID,
) -> dict[str, str]:
    client_uuid = _uuid(client_id)
    if _uuid(confirmed_client_id) != client_uuid:
        raise BrainError("CONFIRMATION_REQUIRED")
    now = datetime.now(timezone.utc)
    with factory.begin() as session:
        row = session.execute(sa.select(tables["clients"]).where(
            tables["clients"].c.id == client_uuid,
        )).mappings().one_or_none()
        if row is None:
            raise BrainError("NOT_FOUND")
        if row["status"] != "revoked":
            session.execute(tables["clients"].update().where(
                tables["clients"].c.id == client_uuid,
            ).values(status="revoked", revoked_at=now,
                     permission_epoch=int(row["permission_epoch"]) + 1))
            session.execute(tables["credentials"].update().where(
                tables["credentials"].c.client_id == client_uuid,
                tables["credentials"].c.revoked_at.is_(None),
            ).values(revoked_at=now))
        _audit(session, tables, owner_id=row["owner_id"], client_id=client_uuid,
               action="revoke_client",
               scope="operations", target_category="client", target_id=client_uuid)
    return {"client_id": str(client_uuid), "status": "revoked"}


def set_project_access(
    factory: Any, tables: Mapping[str, sa.Table], *, client_id: str | UUID,
    project_id: str | UUID, access: str, confirmed_client_id: str | UUID,
    confirmed_project_id: str | UUID,
) -> dict[str, str]:
    client_uuid, project_uuid = _uuid(client_id), _uuid(project_id)
    if _uuid(confirmed_client_id) != client_uuid or _uuid(confirmed_project_id) != project_uuid:
        raise BrainError("CONFIRMATION_REQUIRED")
    if access not in {"read", "write", "none"}:
        raise ValueError("access must be read, write or none")
    clients, projects, grants = tables["clients"], tables["projects"], tables["permission_grants"]
    scope = f"project:{project_uuid}"
    now = datetime.now(timezone.utc)
    with factory.begin() as session:
        client = session.execute(sa.select(clients).where(clients.c.id == client_uuid)).mappings().one_or_none()
        project = session.execute(sa.select(projects).where(projects.c.id == project_uuid)).mappings().one_or_none()
        if client is None or project is None or project["owner_id"] != client["owner_id"]:
            raise BrainError("NOT_FOUND")
        scopes = set(client["scopes"])
        tools = set(client["allowed_tools"])
        if access == "none":
            scopes.discard(scope)
            action = "revoke_project_access"
        else:
            scopes.add(scope)
            tools.add("project.read")
            if access == "write":
                tools.add("project.write")
            action = "grant_project_access"
            for tool in (("project.read",) if access == "read" else ("project.read", "project.write")):
                exists = session.scalar(sa.select(grants.c.id).where(
                    grants.c.client_id == client_uuid, grants.c.effect == "allow",
                    grants.c.scope_pattern == scope, grants.c.tool_pattern == tool,
                    grants.c.effective_to.is_(None),
                ))
                if exists is None:
                    session.execute(grants.insert().values(
                        id=uuid4(), client_id=client_uuid, effect="allow", scope_pattern=scope,
                        tool_pattern=tool, sensitivity_ceiling="private", effective_from=now,
                        effective_to=None, issuer="owner_local_operator",
                        reason=f"explicit project {access} grant",
                    ))
        session.execute(clients.update().where(clients.c.id == client_uuid).values(
            scopes=sorted(scopes), allowed_tools=sorted(tools),
            permission_epoch=int(client["permission_epoch"]) + 1,
        ))
        _audit(session, tables, owner_id=client["owner_id"], client_id=client_uuid,
               action=action, scope=scope,
               target_category="project", target_id=project_uuid)
    return {"client_id": str(client_uuid), "project_id": str(project_uuid), "access": access}


def list_clients(factory: Any, tables: Mapping[str, sa.Table]) -> list[dict[str, object]]:
    with factory() as session:
        rows = session.execute(sa.select(
            tables["clients"].c.id, tables["clients"].c.display_name,
            tables["clients"].c.client_type, tables["clients"].c.status,
            tables["clients"].c.scopes, tables["clients"].c.allowed_tools,
            tables["clients"].c.permission_epoch,
        ).order_by(tables["clients"].c.display_name)).mappings().all()
    return [{key: (str(value) if key == "id" else value) for key, value in row.items()} for row in rows]
