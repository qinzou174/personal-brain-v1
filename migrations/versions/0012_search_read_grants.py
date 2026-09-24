"""Backfill per-scope search/context read grants for existing clients.

Contract alignment: `search_brain` requires `search.read` and `get_brain_context`
requires `context.read` (tool-contracts.md). Clients provisioned before this
revision hold only domain read tools, so their fuzzy cross-scope retrieval was
denied. This revision grants `search.read`/`context.read` on exactly the content
scopes each active client already holds; it never widens a client's scope set and
creates no new tables.
"""

from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0012_search_read_grants"
down_revision = "0011_notifications"
branch_labels = None
depends_on = None

SOURCE_VERSION = "0011_notifications"
TARGET_VERSION = revision
AFFECTED_CANONICAL = ("PermissionGrant", "Client")
AFFECTED_DERIVED = ()
LOCK_STORAGE_IMPACT = (
    "Backfills permission_grants rows (search.read/context.read per held content scope) "
    "and the matching allowed_tools entries for existing active clients; no table is created."
)
BACKUP_PREREQUISITE = "Any populated target requires an independently verified restore point before migration."
RESTORE_STRATEGY = "Production rollback is restore from the verified pre-migration backup; downgrade is restricted to isolated brain_migration_test_* schemas."
PREFLIGHT_SQL = "SELECT to_regclass('permission_grants') IS NOT NULL AS grants_exist"

CREATED_TABLES = ()
POST_VALIDATION_SQL = (
    "SELECT NOT EXISTS ("
    "SELECT 1 FROM clients c WHERE c.status = 'active' "
    "AND EXISTS (SELECT 1 FROM permission_grants g WHERE g.client_id = c.id AND g.effect = 'allow' "
    "AND g.effective_to IS NULL AND g.scope_pattern IN "
    "('knowledge','finance','todo','self','asset','projects')) "
    "AND (NOT EXISTS (SELECT 1 FROM permission_grants g2 WHERE g2.client_id = c.id "
    "AND g2.tool_pattern = 'search.read' AND g2.effect = 'allow' AND g2.effective_to IS NULL) "
    "OR NOT EXISTS (SELECT 1 FROM permission_grants g3 WHERE g3.client_id = c.id "
    "AND g3.tool_pattern = 'context.read' AND g3.effect = 'allow' AND g3.effective_to IS NULL))"
    ") AS backfill_complete"
)

BACKFILL_TOOLS = ("search.read", "context.read")
CONTENT_SCOPES = ("knowledge", "finance", "todo", "self", "asset", "projects")
BACKFILL_ISSUER = "migration_0012_search_read"


def _clients() -> sa.TableClause:
    return sa.table(
        "clients",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("status", sa.String),
        sa.column("scopes", JSONB),
        sa.column("allowed_tools", JSONB),
    )


def _grants() -> sa.TableClause:
    return sa.table(
        "permission_grants",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("client_id", UUID(as_uuid=True)),
        sa.column("effect", sa.String),
        sa.column("scope_pattern", sa.String),
        sa.column("tool_pattern", sa.String),
        sa.column("sensitivity_ceiling", sa.String),
        sa.column("effective_from", sa.DateTime(timezone=True)),
        sa.column("effective_to", sa.DateTime(timezone=True)),
        sa.column("issuer", sa.String),
        sa.column("reason", sa.String),
    )


def upgrade() -> None:
    bind = op.get_bind()
    clients, grants = _clients(), _grants()
    rows = bind.execute(
        sa.select(clients.c.id, clients.c.scopes, clients.c.allowed_tools).where(
            clients.c.status == "active",
        )
    ).mappings().all()
    for row in rows:
        held = set(row["scopes"] or [])
        scopes = [scope for scope in CONTENT_SCOPES if scope in held]
        if not scopes:
            continue
        tools = set(row["allowed_tools"] or [])
        for tool in BACKFILL_TOOLS:
            already = bind.execute(sa.select(sa.func.count()).select_from(grants).where(
                grants.c.client_id == row["id"], grants.c.tool_pattern == tool,
                grants.c.effect == "allow", grants.c.effective_to.is_(None),
            )).scalar()
            if already:
                continue
            for scope in scopes:
                bind.execute(grants.insert().values(
                    id=uuid4(), client_id=row["id"], effect="allow", scope_pattern=scope,
                    tool_pattern=tool, sensitivity_ceiling="private",
                    effective_from=sa.func.now(), effective_to=None,
                    issuer=BACKFILL_ISSUER, reason="0012 search/context read backfill",
                ))
            tools.add(tool)
        bind.execute(clients.update().where(clients.c.id == row["id"]).values(
            allowed_tools=sorted(tools),
        ))


def downgrade() -> None:
    schema = op.get_bind().scalar(sa.text("SELECT current_schema()"))
    if not isinstance(schema, str) or not schema.startswith("brain_migration_test_"):
        raise RuntimeError("downgrade is limited to isolated synthetic test schemas; restore production from verified backup")
    bind = op.get_bind()
    clients, grants = _clients(), _grants()
    bind.execute(grants.delete().where(
        grants.c.issuer == BACKFILL_ISSUER,
        grants.c.tool_pattern.in_(BACKFILL_TOOLS),
    ))
    rows = bind.execute(
        sa.select(clients.c.id, clients.c.allowed_tools).where(clients.c.status == "active")
    ).mappings().all()
    for row in rows:
        tools = set(row["allowed_tools"] or [])
        changed = False
        for tool in BACKFILL_TOOLS:
            remaining = bind.execute(sa.select(sa.func.count()).select_from(grants).where(
                grants.c.client_id == row["id"], grants.c.tool_pattern == tool,
                grants.c.effective_to.is_(None),
            )).scalar()
            if not remaining and tool in tools:
                tools.discard(tool)
                changed = True
        if changed:
            bind.execute(clients.update().where(clients.c.id == row["id"]).values(
                allowed_tools=sorted(tools),
            ))
