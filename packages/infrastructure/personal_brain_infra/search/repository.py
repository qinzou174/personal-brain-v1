"""Owner/scope-filtered PostgreSQL FTS + pgvector retrieval with RRF."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from uuid import UUID, uuid4

import sqlalchemy as sa

from personal_brain_domain.retrieval.ranking import _signal_reasons, rrf_fuse
from personal_brain_infra.search.tokenization import TOKENIZER_ID, fts_query_text, fts_text

_SENSITIVITY_ORDER = ("normal", "personal", "private", "highly_private")


class PostgresSearchRepository:
    def __init__(self, session_factory: Any, table: sa.Table, *, owner_id: UUID) -> None:
        self._factory = session_factory
        self._table = table
        self.owner_id = owner_id
        with session_factory() as session:
            if session.get_bind().dialect.name != "postgresql":
                raise RuntimeError("PostgresSearchRepository requires PostgreSQL")

    def index(
        self, *, target_type: str, target_id: UUID, authorized_scope: str,
        sensitivity: str, canonicality: str, freshness: str, text: str,
        source_links: Sequence[str], vector_model_version: str | None = None,
        embedding: Sequence[float] | None = None, warnings: Sequence[str] = (),
    ) -> str:
        if sensitivity not in _SENSITIVITY_ORDER:
            raise ValueError("secret/unknown sensitivity cannot enter search")
        if embedding is not None and not vector_model_version:
            raise ValueError("embedding requires a model version")
        now, entry_id = datetime.now(timezone.utc), uuid4()
        metadata = {
            "source_links": list(source_links), "warnings": list(warnings),
            "tokenizer": TOKENIZER_ID,
            "embedding_dimensions": None if embedding is None else len(embedding),
            "display_excerpt": text[:300],
        }
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
        return str(entry_id)

    def search(
        self, *, query: str, authorized_scope: str, sensitivity_ceiling: str,
        query_embedding: Sequence[float] | None = None,
        vector_model_version: str | None = None, limit: int = 20,
    ) -> list[dict[str, Any]]:
        allowed = _SENSITIVITY_ORDER[:_SENSITIVITY_ORDER.index(sensitivity_ceiling) + 1]
        base = (
            self._table.c.owner_id == self.owner_id,
            self._table.c.authorized_scope == authorized_scope,
            self._table.c.sensitivity.in_(allowed),
            self._table.c.valid_to.is_(None),
        )
        tsquery = sa.func.websearch_to_tsquery("simple", fts_query_text(query))
        keyword_stmt = sa.select(
            self._table,
            sa.func.ts_rank_cd(self._table.c.search_document, tsquery).label("keyword_score"),
        ).where(*base, self._table.c.search_document.op("@@")(tsquery)).order_by(
            sa.desc("keyword_score"), self._table.c.id,
        ).limit(50)
        semantic_rows: list[Mapping[str, Any]] = []
        with self._factory() as session:
            keyword_rows = session.execute(keyword_stmt).mappings().all()
            if query_embedding is not None and vector_model_version:
                distance = self._table.c.embedding.cosine_distance(list(query_embedding))
                semantic_stmt = sa.select(self._table, distance.label("distance")).where(
                    *base, self._table.c.embedding.is_not(None),
                    self._table.c.vector_model_version == vector_model_version,
                ).order_by(distance, self._table.c.id).limit(50)
                semantic_rows = session.execute(semantic_stmt).mappings().all()
        keyword_ids = [row["id"] for row in keyword_rows]
        semantic_ids = [row["id"] for row in semantic_rows]
        scores = rrf_fuse(keyword_rank=keyword_ids, semantic_rank=semantic_ids)
        by_id = {row["id"]: row for row in [*keyword_rows, *semantic_rows]}

        def _length_penalty(row: Mapping[str, Any]) -> float:
            """Weight short, precise records above long multi-topic documents.

            jieba search-mode tokenization splits short phrases (拿铁 -> 拿/铁),
            so keyword rank favors longer documents that OR-match more segments;
            whole-document embeddings likewise average long archives across many
            topics. Without a length term, personal archives drown out exact
            diary/expense records (O2). Penalty is monotone and capped (>= 0.1).
            """
            length = len(row.get("searchable_text") or "")
            if length <= 400:
                return 1.0
            return max(0.1, 400.0 / length)

        ranked = sorted(
            scores,
            key=lambda item: (-(scores[item] * _length_penalty(by_id[item])), str(item)),
        )[:limit]
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
