"""Versioned derivations over verified original asset bytes."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID, uuid4

import sqlalchemy as sa

from personal_brain_domain.common.errors import BrainError
from personal_brain_infra.persistence.unit_of_work import UnitOfWork
from personal_brain_infra.storage.base import StorageBackend


class AssetDerivationService:
    def __init__(self, session_factory: Any, tables: dict[str, sa.Table], *,
                 owner_id: UUID, storage: StorageBackend) -> None:
        required = {"assets", "asset_blobs", "derived_contents", "derivation_edges"}
        if not required <= set(tables):
            raise RuntimeError(f"asset schema missing tables: {sorted(required - set(tables))}")
        self._factory = session_factory
        self._tables = tables
        self._owner_id = owner_id
        self._storage = storage

    @staticmethod
    def _db_id(table: sa.Table, column: str, value: UUID) -> UUID | str:
        kind = table.c[column].type
        if isinstance(kind, sa.Uuid) and kind.as_uuid:
            return value
        if isinstance(kind, sa.String) and kind.length == 32:
            return value.hex
        return str(value)

    def process(
        self, *, asset_id: UUID, kind: str, generator_kind: str,
        generator_version: str, transform: Callable[[bytes], bytes],
    ) -> dict[str, Any]:
        if kind not in {"extracted_text", "transcript", "description", "embedding"}:
            raise BrainError("VALIDATION_FAILED")
        assets, blobs = self._tables["assets"], self._tables["asset_blobs"]
        derived, edges = self._tables["derived_contents"], self._tables["derivation_edges"]
        owner_asset = self._db_id(assets, "owner_id", self._owner_id)
        asset_key = self._db_id(assets, "id", asset_id)
        with self._factory() as session:
            asset = session.execute(sa.select(assets).where(
                assets.c.id == asset_key, assets.c.owner_id == owner_asset,
            )).mappings().one_or_none()
            if asset is None:
                raise BrainError("NOT_FOUND")
            blob = session.execute(sa.select(blobs).where(
                blobs.c.id == asset["blob_id"],
                blobs.c.owner_id == self._db_id(blobs, "owner_id", self._owner_id),
            )).mappings().one()
            existing = session.execute(sa.select(derived).where(
                derived.c.owner_id == self._db_id(derived, "owner_id", self._owner_id),
                derived.c.target_type == "asset", derived.c.target_id == asset_key,
                derived.c.kind == kind, derived.c.derivation_version == generator_version,
            )).mappings().one_or_none()
            if existing is not None:
                return {"derived_id": str(existing["id"]), "payload_ref": existing["payload_ref"], "replayed": True}
        original = self._storage.read(blob["storage_key"])
        if len(original) != int(blob["size_bytes"]) or hashlib.sha256(original).hexdigest() != blob["sha256"]:
            raise BrainError("DEPENDENCY_CONFLICT")
        output = transform(original)
        if not isinstance(output, bytes) or not output:
            raise BrainError("VALIDATION_FAILED")
        output_hash = hashlib.sha256(output).hexdigest()
        stored = self._storage.store_atomic(
            __import__("io").BytesIO(output), expected_sha256=output_hash,
            expected_size=len(output), content_type="application/octet-stream",
        )
        derived_id, edge_id = uuid4(), uuid4()
        now = datetime.now(timezone.utc)
        with UnitOfWork(self._factory) as uow:
            session = uow.session
            session.execute(derived.insert().values(
                id=self._db_id(derived, "id", derived_id),
                owner_id=self._db_id(derived, "owner_id", self._owner_id),
                target_type="asset", target_id=self._db_id(derived, "target_id", asset_id),
                kind=kind, derivation_version=generator_version,
                generator_kind=generator_kind, generator_version=generator_version,
                derived_at=now, confidence="deterministic", confidence_inputs={"input_sha256": blob["sha256"]},
                payload_ref=stored.storage_key, state="active", sensitivity="normal",
                information_class="ai_extraction", canonicality="derived", source_kind="ai_extraction",
                source_id=self._db_id(derived, "source_id", asset_id), valid_from=now,
                valid_to=None, lifecycle_state="active", deleted_at=None,
            ))
            session.execute(edges.insert().values(
                id=self._db_id(edges, "id", edge_id),
                owner_id=self._db_id(edges, "owner_id", self._owner_id),
                source_type="asset", source_id=self._db_id(edges, "source_id", asset_id),
                derived_type="derived_content", derived_id=self._db_id(edges, "derived_id", derived_id),
                role="extracted_from", contribution_weight=1, generator_version=generator_version,
            ))
            session.execute(assets.update().where(assets.c.id == asset_key).values(
                integrity_state="valid", processing_state="ready",
            ))
            uow.commit()
        return {"derived_id": str(derived_id), "payload_ref": stored.storage_key, "replayed": False}
