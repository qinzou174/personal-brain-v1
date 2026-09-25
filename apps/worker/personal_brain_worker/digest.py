"""Daily digest: a retrievable navigation layer over the previous local day.

Δ4 / D3(a): the digest is generated every day from the previous local calendar
day's canonical raw inputs, grouped by authorization scope so a scope-limited
reader can never see another scope's content through a digest.  The summary is
persisted as ``derived_contents`` (kind=digest) with a stored payload, lineage
edges to every contributing raw input and full ``source_links`` — it navigates
the originals and never replaces them (FR-078/FR-094).

Empty days produce nothing (``skipped=empty_window``); a missing provider is
reported honestly; the shared daily LLM job quota bounds the work.
"""

from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable, Mapping
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5
from zoneinfo import ZoneInfo

import sqlalchemy as sa

from personal_brain_domain.common.errors import BrainError
from personal_brain_domain.security.secret_filter import detect_secret
from personal_brain_infra.models.gateway import ModelGateway, ProviderCallBudget
from personal_brain_infra.storage.base import StorageBackend
from personal_brain_worker.llm_budget import quota_exceeded
from personal_brain_worker.runtime import JobExecutionError

DIGEST_VERSION = "digest-v1"
# The gateway bounds the whole encoded request to 64KiB; CJK text is ~3 bytes per
# character, so the bundle stays well inside that ceiling.
MAX_BUNDLE_CHARS = 12000
_SENSITIVITY_ORDER = ("normal", "personal", "private", "highly_private")

_DIGEST_INSTRUCTION = (
    "你是个人知识库的每日摘要器。仅根据给出的当日记录生成 3-6 条中文要点摘要"
    "（每行以“- ”开头），忠实于记录内容，不补充未记录的事实，不给出建议。"
)


def utcnow() -> datetime:
    """Current UTC time (module-level seam so tests can pin the digest clock)."""
    return datetime.now(timezone.utc)


def digest_window(now_utc: datetime, timezone_name: str) -> tuple[datetime, datetime, str]:
    """The previous local calendar day as a half-open UTC interval plus its label."""
    local = now_utc.astimezone(ZoneInfo(timezone_name))
    today_start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    start = today_start - timedelta(days=1)
    return start.astimezone(ZoneInfo("UTC")), today_start.astimezone(ZoneInfo("UTC")), start.date().isoformat()


def _scope_sensitivity(rows: list[Mapping[str, Any]]) -> str:
    worst = "normal"
    for row in rows:
        value = row["sensitivity"]
        if value in _SENSITIVITY_ORDER and _SENSITIVITY_ORDER.index(value) > _SENSITIVITY_ORDER.index(worst):
            worst = value
    return worst


def make_digest_handler(
    session_factory: Any, tables: Mapping[str, sa.Table], storage: StorageBackend | None,
    gateway: ModelGateway | None, embedder: Any | None = None, *, quota: int = 200,
    timezone_name: str = "Asia/Shanghai",
) -> Callable[..., dict[str, Any]]:
    def handler(job: dict[str, Any], context: Any) -> dict[str, Any]:
        owner_id = UUID(str(job["owner_id"]))
        moment = utcnow()
        raws, intakes = tables["raw_inputs"], tables["intake_requests"]
        derived, edges = tables["derived_contents"], tables["derivation_edges"]
        start, end, label = digest_window(moment, timezone_name)
        with session_factory() as session:
            rows = session.execute(sa.select(raws, intakes.c.requested_scope).join(
                intakes, intakes.c.id == raws.c.intake_request_id,
            ).where(
                raws.c.owner_id == owner_id, raws.c.lifecycle_state == "active",
                raws.c.content_text.is_not(None),
                raws.c.original_at >= start, raws.c.original_at < end,
            ).order_by(raws.c.original_at, raws.c.id)).mappings().all()
        if not rows:
            return {"skipped": "empty_window", "date": label}
        if not isinstance(gateway, ModelGateway) or gateway.provider is None or gateway.card is None:
            return {"skipped": "provider_unavailable"}
        if storage is None:
            raise JobExecutionError("TOOL_DENIED", retryable=False)
        with session_factory() as session:
            if quota_exceeded(
                session, tables["jobs"], owner_id=owner_id, now_utc=moment,
                timezone_name=timezone_name, quota=quota,
            ):
                return {"skipped": "daily_quota_exceeded", "quota": quota}

        groups: dict[str, list[Mapping[str, Any]]] = {}
        for row in rows:
            groups.setdefault(row["requested_scope"], []).append(row)
        # Every scope that recorded something yesterday gets its digest — the old
        # 5-scope cap silently dropped the rest of the day. Cost stays bounded by
        # the shared daily LLM job quota (the same budget extraction draws from),
        # and existing digests are replay-skipped before any model call.
        selected = sorted(groups)
        dropped_scopes = 0
        zone = ZoneInfo(timezone_name)
        digests = skipped_scopes = secret_skipped_scopes = secret_excluded = 0
        for scope in selected:
            items = groups[scope]
            digest_id = uuid5(NAMESPACE_URL, f"brain-digest:{owner_id}:{scope}:{label}")
            with session_factory() as session:
                exists = session.scalar(sa.select(derived.c.id).where(
                    derived.c.owner_id == owner_id, derived.c.target_type == "scope",
                    derived.c.target_id == digest_id, derived.c.kind == "digest",
                    derived.c.derivation_version == DIGEST_VERSION,
                ))
            if exists is not None:
                skipped_scopes += 1
                continue
            # Decision (b), 2026-09-25: secret-like records are never sent to a
            # provider. They keep their place in the digest as a value-free marker
            # (timing + source link stay navigable); a scope made up entirely of
            # such records produces no model call at all.
            lines, scope_secret = [], 0
            for row in items:
                stamp = f"[{row['original_at'].astimezone(zone):%H:%M}] "
                text = (row["content_text"] or "").strip().replace(chr(10), " ")
                if detect_secret(
                    filename="digest-input.txt", content_type="text/plain", content=text,
                ).matched:
                    scope_secret += 1
                    lines.append(f"{stamp}[疑似凭据内容，未发送给模型]")
                else:
                    lines.append(f"{stamp}{text[:500]}")
            if scope_secret == len(items):
                secret_skipped_scopes += 1
                continue
            secret_excluded += scope_secret
            bundle = "\n".join(lines)[:MAX_BUNDLE_CHARS]
            source_links = [f"raw_input:{row['id']}" for row in items]
            sensitivity = _scope_sensitivity(items)
            context.progress(30, f"bounded digest call for scope {scope}")
            try:
                result = gateway.execute(
                    {"prompt": f"{_DIGEST_INSTRUCTION}\n\n<当日记录>\n{bundle}\n</当日记录>",
                     "max_tokens": 1200, "thinking": {"type": "disabled"}},
                    {"target_type": "scope", "payload_ref": f"digest:{label}",
                     "kind": "daily_digest", "sources": source_links[:20]},
                    sensitivity=sensitivity, budget=ProviderCallBudget(max_calls=1),
                )
            except BrainError as error:
                if error.code == "SECRET_REJECTED":
                    # Defence in depth: a declared skip, never a dead letter.
                    secret_skipped_scopes += 1
                    continue
                raise JobExecutionError(
                    error.code, retryable=error.code in {"BRAIN_UNAVAILABLE", "DEPENDENCY_CONFLICT"},
                ) from error
            summary = str(result.get("text", "")).strip()
            if not summary:
                raise JobExecutionError("BRAIN_UNAVAILABLE", retryable=True)
            payload = {"summary": summary, "scope": scope, "date": label,
                       "source_links": source_links, "model": result.get("model"),
                       "digest_version": DIGEST_VERSION}
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            stored = storage.store_atomic(
                io.BytesIO(encoded), expected_sha256=hashlib.sha256(encoded).hexdigest(),
                expected_size=len(encoded), content_type="application/json",
            )
            share = Decimal(str(round(1.0 / len(items), 4)))
            with session_factory.begin() as session:
                session.execute(derived.insert().values(
                    id=digest_id, owner_id=owner_id, target_type="scope", target_id=digest_id,
                    kind="digest", derivation_version=DIGEST_VERSION,
                    generator_kind="model", generator_version=DIGEST_VERSION,
                    derived_at=moment, confidence="model_generated",
                    confidence_inputs={"model": result.get("model"), "source_count": len(items),
                                       "window_start": start.isoformat(), "window_end": end.isoformat()},
                    payload_ref=stored.storage_key, state="active", sensitivity=sensitivity,
                    information_class="ai_extraction", canonicality="derived",
                    source_kind="ai_extraction", source_id=items[0]["id"], valid_from=moment,
                    valid_to=None, lifecycle_state="active", deleted_at=None,
                ))
                for row in items:
                    session.execute(edges.insert().values(
                        id=uuid4(), owner_id=owner_id, source_type="raw_input", source_id=row["id"],
                        derived_type="derived_content", derived_id=digest_id,
                        role="summarized_from", contribution_weight=share,
                        generator_version=DIGEST_VERSION,
                    ))
            _index_digest(
                session_factory, tables["search_index_entries"], embedder, owner_id=owner_id,
                digest_id=digest_id, scope=scope, sensitivity=sensitivity,
                text=summary, source_links=source_links, content_time=moment.isoformat(),
            )
            digests += 1
        context.progress(100, "daily digests committed")
        return {"digests": digests, "skipped_scopes": skipped_scopes,
                "dropped_scopes": len(groups) - len(selected), "scopes": selected, "date": label,
                "secret_excluded": secret_excluded, "secret_skipped_scopes": secret_skipped_scopes}

    return handler


def _index_digest(
    session_factory: Any, index_table: sa.Table, embedder: Any | None, *,
    owner_id: UUID, digest_id: UUID, scope: str, sensitivity: str,
    text: str, source_links: list[str], content_time: str | None = None,
) -> None:
    """Project the digest into retrieval (PostgreSQL deployments only)."""
    with session_factory() as session:
        if session.get_bind().dialect.name != "postgresql":
            return
    from personal_brain_infra.search.repository import PostgresSearchRepository

    embedding = vector_model_version = None
    if embedder is not None:
        try:
            embedding = embedder.embed(text)
            vector_model_version = embedder.model_version
        except BrainError:
            # A failed embedding must not lose the digest: it stays keyword-searchable.
            embedding = vector_model_version = None
    repository = PostgresSearchRepository(session_factory, index_table, owner_id=owner_id)
    repository.index(
        target_type="derived_content", target_id=digest_id, authorized_scope=scope,
        sensitivity=sensitivity, canonicality="derived", freshness="fresh",
        text=text, source_links=source_links, embedding=embedding,
        vector_model_version=vector_model_version,
        content_time=content_time,
    )