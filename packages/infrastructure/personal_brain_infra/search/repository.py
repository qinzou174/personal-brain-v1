"""Owner/scope-filtered PostgreSQL FTS + pgvector retrieval with RRF."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from uuid import UUID, uuid4

import sqlalchemy as sa

from personal_brain_domain.retrieval.ranking import _signal_reasons, rrf_fuse
from personal_brain_infra.search.tokenization import TOKENIZER_ID, fts_query_text, fts_text

SENSITIVITY_ORDER = ("normal", "personal", "private", "highly_private")
_SENSITIVITY_ORDER = SENSITIVITY_ORDER  # legacy private alias


class PostgresSearchRepository:
    def __init__(self, session_factory: Any, table: sa.Table, *, owner_id: UUID,
                 chunk_table: sa.Table | None = None) -> None:
        self._factory = session_factory
        self._table = table
        self._chunk_table = chunk_table
        self.owner_id = owner_id
        with session_factory() as session:
            if session.get_bind().dialect.name != "postgresql":
                raise RuntimeError("PostgresSearchRepository requires PostgreSQL")

    def index(
        self, *, target_type: str, target_id: UUID, authorized_scope: str,
        sensitivity: str, canonicality: str, freshness: str, text: str,
        source_links: Sequence[str], vector_model_version: str | None = None,
        embedding: Sequence[float] | None = None, warnings: Sequence[str] = (),
        content_time: str | None = None,
        chunks: Sequence[tuple[str, Sequence[float]]] | None = None,
    ) -> str:
        if sensitivity not in _SENSITIVITY_ORDER:
            raise ValueError("secret/unknown sensitivity cannot enter search")
        if embedding is not None and not vector_model_version:
            raise ValueError("embedding requires a model version")
        if chunks:
            # A card is either whole-vector (short) or chunked (long): the
            # diluted whole-doc average must never compete with its own chunks.
            if self._chunk_table is None:
                raise ValueError("chunk indexing requires the search_index_chunks table")
            if not vector_model_version:
                raise ValueError("chunked indexing requires a model version")
            if embedding is not None:
                raise ValueError("a card cannot carry both a whole vector and chunks")
        now, entry_id = datetime.now(timezone.utc), uuid4()
        metadata = {
            "source_links": list(source_links), "warnings": list(warnings),
            "tokenizer": TOKENIZER_ID,
            "embedding_dimensions": None if embedding is None else len(embedding),
            "display_excerpt": text[:300],
        }
        if content_time:
            # R4/N-04: the record's own time, enabling range-filtered recall
            # without a per-hit join back to the source table.
            metadata["content_time"] = content_time
        with self._factory.begin() as session:
            session.execute(self._table.delete().where(
                self._table.c.owner_id == self.owner_id,
                self._table.c.target_type == target_type,
                self._table.c.target_id == target_id,
                self._table.c.vector_model_version.is_not_distinct_from(vector_model_version),
            ))
            session.execute(self._table.insert().values(
                id=entry_id, owner_id=self.owner_id, target_type=target_type, target_id=target_id,
                authorized_scope=authorized_scope, sensitivity=sensitivity,
                canonicality=canonicality, valid_from=now, valid_to=None, freshness=freshness,
                searchable_text=fts_text(text), embedding=None if embedding is None else list(embedding),
                vector_model_version=vector_model_version, metadata_filters=metadata, indexed_at=now,
            ))
            if chunks:
                # Chunk lifetime is subordinate to the parent card: this new
                # entry_id owns the fresh rows, and any prior card for the same
                # target (same model version) was deleted above, cascading its
                # chunks away. No separate chunk-replacement step can race.
                session.execute(self._chunk_table.insert().values([
                    {
                        "id": uuid4(), "owner_id": self.owner_id, "entry_id": entry_id,
                        "chunk_seq": seq, "chunk_text": chunk_text,
                        "embedding": list(chunk_vector),
                        "vector_model_version": vector_model_version,
                    }
                    for seq, (chunk_text, chunk_vector) in enumerate(chunks)
                ]))
        return str(entry_id)

    def search(
        self, *, query: str, authorized_scope: str, sensitivity_ceiling: str,
        query_embedding: Sequence[float] | None = None,
        vector_model_version: str | None = None, limit: int = 20,
        time_from: str | None = None, time_to: str | None = None,
    ) -> list[dict[str, Any]]:
        allowed = _SENSITIVITY_ORDER[:_SENSITIVITY_ORDER.index(sensitivity_ceiling) + 1]
        base = [
            self._table.c.owner_id == self.owner_id,
            self._table.c.authorized_scope == authorized_scope,
            self._table.c.sensitivity.in_(allowed),
            self._table.c.valid_to.is_(None),
        ]
        if time_from is not None or time_to is not None:
            # R4: when a range is requested, cards without a content_time are
            # honestly excluded — a NULL comparison never matches, so they
            # cannot masquerade as in-range hits.
            content_time = self._table.c.metadata_filters.op("->>")("content_time")
            if time_from is not None:
                base.append(content_time >= time_from)
            if time_to is not None:
                base.append(content_time <= time_to)
        tsquery = sa.func.websearch_to_tsquery("simple", fts_query_text(query))
        # ER-03: RRF is the only cross-list ranking authority, so document length
        # must never scale the *fused* score. RRF scores live in a ~1/60 band
        # (0.009..0.033), while a multiplicative length penalty spans 10x: it ends
        # up ranking by length instead of relevance and hides long records
        # entirely. Observed regression (chain-audit 2026-09-24): a long archive
        # that was the only lexical match (keyword rank 1) *and* semantic rank 1
        # for the query "壁纸" still dropped out of the top 30, because 400/2031
        # scaled its fused score from the best to below every short note.
        # ts_rank_cd's own length bias (jieba OR-matches accumulate in long
        # documents) is corrected inside the keyword list instead, BM25-style:
        # keyword score per log-length, i.e. match density.
        document_length = sa.func.greatest(sa.func.length(self._table.c.searchable_text), 1)
        keyword_density = (
            sa.func.ts_rank_cd(self._table.c.search_document, tsquery)
            / (1.0 + sa.func.ln(document_length))
        ).label("keyword_density")
        keyword_stmt = sa.select(self._table, keyword_density).where(
            *base, self._table.c.search_document.op("@@")(tsquery),
        ).order_by(sa.desc("keyword_density"), self._table.c.id).limit(50)
        semantic_rows: list[Mapping[str, Any]] = []
        with self._factory() as session:
            keyword_rows = session.execute(keyword_stmt).mappings().all()
            if query_embedding is not None and vector_model_version:
                # ER-03: RRF is the only cross-list ranking authority — these two
                # lists only feed it. The semantic list is assembled from two
                # sources: focused chunks (long docs, one row per parent card via
                # DISTINCT ON = max chunk score) and the legacy whole-card vector
                # (short docs). Chunked cards carry no whole-doc vector, so the
                # sources are disjoint by construction; the per-card min-distance
                # merge only guards side-by-side model-version leftovers.
                candidates: list[Mapping[str, Any]] = []
                if self._chunk_table is not None:
                    chunk_distance = self._chunk_table.c.embedding.cosine_distance(list(query_embedding))
                    chunk_stmt = sa.select(
                        self._table, chunk_distance.label("distance"),
                    ).select_from(self._chunk_table.join(
                        self._table, self._chunk_table.c.entry_id == self._table.c.id,
                    )).where(
                        *base, self._chunk_table.c.vector_model_version == vector_model_version,
                    ).distinct(self._table.c.id).order_by(
                        self._table.c.id, chunk_distance,
                    ).limit(50)
                    candidates.extend(session.execute(chunk_stmt).mappings().all())
                distance = self._table.c.embedding.cosine_distance(list(query_embedding))
                semantic_stmt = sa.select(self._table, distance.label("distance")).where(
                    *base, self._table.c.embedding.is_not(None),
                    self._table.c.vector_model_version == vector_model_version,
                ).order_by(distance, self._table.c.id).limit(50)
                candidates.extend(session.execute(semantic_stmt).mappings().all())
                best: dict[Any, Mapping[str, Any]] = {}
                for row in candidates:
                    known = best.get(row["id"])
                    if known is None or row["distance"] < known["distance"]:
                        best[row["id"]] = row
                semantic_rows = sorted(
                    best.values(), key=lambda row: (row["distance"], str(row["id"])),
                )[:50]
        keyword_ids = [row["id"] for row in keyword_rows]
        semantic_ids = [row["id"] for row in semantic_rows]
        scores = rrf_fuse(keyword_rank=keyword_ids, semantic_rank=semantic_ids)
        by_id = {row["id"]: row for row in [*keyword_rows, *semantic_rows]}

        ranked = sorted(scores, key=lambda item: (-scores[item], str(item)))[:limit]
        results = []
        for entry_id in ranked:
            row = by_id[entry_id]
            metadata = dict(row["metadata_filters"] or {})
            warnings = list(metadata.get("warnings") or [])
            if row["freshness"] != "fresh":
                warnings.append(f"freshness:{row['freshness']}")
            reasons = _signal_reasons({
                "freshness": row["freshness"],
                "confidence": metadata.get("confidence"),
                "information_class": row["canonicality"],
                "source_trust": metadata.get("source_trust"),
            }) or ("rrf",)
            results.append({
                "entry_id": str(entry_id), "target_type": row["target_type"],
                "target_id": str(row["target_id"]), "scope": row["authorized_scope"],
                "excerpt": metadata.get("display_excerpt", (row["searchable_text"] or "")[:300]),
                "score": scores[entry_id],
                "freshness": row["freshness"], "canonicality": row["canonicality"],
                "source_links": list(metadata.get("source_links") or []),
                "warnings": list(dict.fromkeys(warnings)),
                "vector_model_version": row["vector_model_version"],
                "ranking_reasons": list(reasons),
            })
        return results
