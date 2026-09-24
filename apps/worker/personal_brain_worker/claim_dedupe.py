"""Deterministic duplicate control for self claims (D2, 2026-09-25).

The extraction pipeline used to append every model-proposed claim as a new
candidate, so the owner profile accumulated identical and near-identical rows
(the live instance showed one claim three times plus clusters of paraphrases).
Duplicate control is a *rule*, not a model judgement:

- ``normalize_claim`` (shared with ``evolution``) makes surface form irrelevant;
- token overlap (jieba, the retrieval tokenizer) measures likeness: at or above
  ``MERGE_SIMILARITY`` the rows are the same claim, so evidence moves to the
  surviving row and the duplicate is superseded with a correction event (never
  deleted, never silently rewritten);
- stored claim vectors (the same ones retrieval uses) add a *suspicion* band:
  ``VECTOR_SUSPICION`` <= cosine < 1.0 opens one ``merge_candidate`` review item
  and changes nothing else (D4=a: wording-different paraphrases are the owner's
  decision; approving the item executes the merge);
- inside [``REVIEW_SIMILARITY``, ``MERGE_SIMILARITY``) token overlap is also a
  suspicion, never a merge;
- opposite polarity never merges — that is the conflict path, not a duplicate.

The same rule runs twice: at extraction time a duplicate candidate attaches its
evidence to the claim that already exists instead of creating a row, and the
daily ``dedupe_claims`` sweep cleans rows that predate the rule.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import sqlalchemy as sa

from personal_brain_worker.evolution import is_negative, normalize_claim

MERGE_SIMILARITY = 0.75
REVIEW_SIMILARITY = 0.5
VECTOR_SUSPICION = 0.85
MAX_DEDUPE_SCAN = 500
_LIVE_STATES = ("candidate", "active", "historical")


def claim_tokens(text: Any) -> frozenset[str]:
    """Token set of a claim using the retrieval tokenizer (stable, offline)."""
    from personal_brain_infra.search.tokenization import tokenize

    return frozenset(tokenize(str(text or "")))


def claim_similarity(left: Any, right: Any) -> float:
    """Jaccard overlap of two claim token sets (0.0..1.0)."""
    left_tokens, right_tokens = claim_tokens(left), claim_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def duplicate_kind(candidate: Any, existing: Any) -> str:
    """``duplicate`` (merge), ``suspected`` (review) or ``distinct`` (leave alone)."""
    if is_negative(candidate) != is_negative(existing):
        return "distinct"
    if normalize_claim(candidate) == normalize_claim(existing):
        return "duplicate"
    similarity = claim_similarity(candidate, existing)
    if similarity >= MERGE_SIMILARITY:
        return "duplicate"
    if similarity >= REVIEW_SIMILARITY:
        return "suspected"
    return "distinct"


def find_duplicate(
    claim: str, existing_rows: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], str, float] | None:
    """Best matching existing row for a candidate claim text, if any.

    ``existing_rows`` are claim rows (mappings with ``claim`` and ``id``); the
    caller is responsible for pre-filtering owner and category.
    """
    best: tuple[Mapping[str, Any], str, float] | None = None
    for row in existing_rows:
        kind = duplicate_kind(claim, row["claim"])
        if kind == "distinct":
            continue
        similarity = claim_similarity(claim, row["claim"])
        if normalize_claim(claim) == normalize_claim(row["claim"]):
            similarity = 1.0
        if best is None or similarity > best[2]:
            best = (row, kind, similarity)
    return best


def _correction_events(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(event) for event in (row["correction_events"] or [])]


def _survivor_rank(row: Mapping[str, Any], evidence_counts: Mapping[Any, int]) -> tuple:
    """Established and better-evidenced rows win; ties go to the older one."""
    established = row["establishment"] == "established" or row["lifecycle_state"] == "active"
    return (
        0 if established else 1,
        -int(evidence_counts.get(row["id"], 0)),
        row["created_at"],
        str(row["id"]),
    )


def make_dedupe_handler(
    session_factory: Any, tables: Mapping[str, sa.Table], *,
    now: Callable[[], datetime] | None = None,
) -> Callable[..., dict[str, Any]]:
    clock = now or (lambda: datetime.now(timezone.utc))

    def handler(job: dict[str, Any], context: Any) -> dict[str, Any]:
        owner_id = UUID(str(job["owner_id"]))
        moment = clock()
        claims, evidence = tables["self_claims"], tables["evidence"]
        index_entries, items, jobs = (
            tables["search_index_entries"], tables["review_inbox_items"], tables["jobs"],
        )
        merged = superseded = suspected_items = 0
        groups_count = 0
        with session_factory.begin() as session:
            rows = session.execute(sa.select(claims).where(
                claims.c.owner_id == owner_id,
                claims.c.lifecycle_state.in_(_LIVE_STATES),
            ).limit(MAX_DEDUPE_SCAN)).mappings().all()
            buckets: dict[tuple[str, bool], list[Mapping[str, Any]]] = {}
            for row in rows:
                buckets.setdefault((row["category"], is_negative(row["claim"])), []).append(row)
            evidence_counts: dict[Any, int] = {}
            if rows:
                evidence_counts = {
                    row[0]: int(row[1]) for row in session.execute(sa.select(
                        evidence.c.target_id, sa.func.count(),
                    ).where(
                        evidence.c.owner_id == owner_id,
                        evidence.c.target_type == "self_claim",
                        evidence.c.target_id.in_([row["id"] for row in rows]),
                    ).group_by(evidence.c.target_id)).all()
                }

            def open_merge_item(left: Mapping[str, Any], right: Mapping[str, Any],
                                similarity: float, reason: str) -> None:
                nonlocal suspected_items
                pair = frozenset({str(left["id"]), str(right["id"])})
                if pair in known_pairs or pair & claimed_refs:
                    return
                item_id = uuid4()
                survivor = sorted(
                    (left, right), key=lambda row: _survivor_rank(row, evidence_counts),
                )[0]
                session.execute(items.insert().values(
                    id=item_id, owner_id=owner_id, item_type="merge_candidate",
                    subject_refs=sorted(pair),
                    proposal={"kind": reason, "category": left["category"],
                              "survivor_id": str(survivor["id"]),
                              "claims": sorted({left["claim"], right["claim"]}),
                              "similarity": round(similarity, 4)},
                    risk="ordinary",
                    evidence=[{"source_ids": sorted({
                        str(left["source_id"]), str(right["source_id"])})}],
                    state="open", resolver_id=None, resolved_at=None,
                    expires_at=None, expected_version=1,
                ))
                session.execute(jobs.insert().values(
                    id=uuid4(), owner_id=owner_id, client_id=None,
                    job_type="notify_review", payload_ref=f"review_item:{item_id}",
                    idempotency_key=uuid5(NAMESPACE_URL, f"brain-merge-review:{item_id}"),
                    state="queued", priority=0, attempts=0, max_attempts=5,
                    available_at=moment, claim_token=0,
                ))
                known_pairs.add(pair)
                claimed_refs.update(pair)
                suspected_items += 1

            open_items = session.execute(sa.select(items.c.subject_refs).where(
                items.c.owner_id == owner_id,
                items.c.item_type == "merge_candidate",
                items.c.state.in_(("open", "deferred")),
            )).mappings().all()
            known_pairs = {frozenset(str(ref) for ref in (row["subject_refs"] or []))
                           for row in open_items}
            # One merge_candidate per claim keeps a topic cluster reviewable as a
            # whole instead of producing every pairwise combination.
            claimed_refs = {ref for pair in known_pairs for ref in pair}

            for group in buckets.values():
                if len(group) < 2:
                    continue
                parent = list(range(len(group)))

                def find(index: int) -> int:
                    while parent[index] != index:
                        parent[index] = parent[parent[index]]
                        index = parent[index]
                    return index

                def union(left: int, right: int) -> None:
                    left_root, right_root = find(left), find(right)
                    if left_root != right_root:
                        parent[right_root] = left_root

                for left_index, left in enumerate(group):
                    for right_index in range(left_index + 1, len(group)):
                        right = group[right_index]
                        kind = duplicate_kind(left["claim"], right["claim"])
                        if kind == "duplicate":
                            union(left_index, right_index)
                        elif kind == "suspected":
                            open_merge_item(left, right, claim_similarity(
                                left["claim"], right["claim"],
                            ), "suspected_duplicate_claim")

                # Wording-different paraphrases share no tokens; their stored
                # retrieval vectors are the only offline evidence of likeness.
                vectors = _claim_vectors(session, tables, owner_id, group, index_entries)
                for left_index, left in enumerate(group):
                    for right_index in range(left_index + 1, len(group)):
                        right = group[right_index]
                        if find(left_index) == find(right_index):
                            continue
                        left_vector, right_vector = vectors.get(left["id"]), vectors.get(right["id"])
                        if left_vector is None or right_vector is None:
                            continue
                        similarity = cosine_similarity(left_vector, right_vector)
                        if similarity >= VECTOR_SUSPICION:
                            open_merge_item(left, right, similarity, "suspected_paraphrase")

                merged_groups: dict[int, list[Mapping[str, Any]]] = {}
                for index, row in enumerate(group):
                    merged_groups.setdefault(find(index), []).append(row)
                for members in merged_groups.values():
                    if len(members) < 2:
                        continue
                    groups_count += 1
                    survivor = sorted(
                        members, key=lambda row: _survivor_rank(row, evidence_counts),
                    )[0]
                    duplicates = [row for row in members if row["id"] != survivor["id"]]
                    merged_ids = [str(row["id"]) for row in duplicates]
                    for duplicate in duplicates:
                        session.execute(evidence.update().where(
                            evidence.c.owner_id == owner_id,
                            evidence.c.target_type == "self_claim",
                            evidence.c.target_id == duplicate["id"],
                        ).values(target_id=survivor["id"], version=evidence.c.version + 1,
                                 updated_at=moment))
                        events = _correction_events(duplicate)
                        events.append({"type": "superseded_by_duplicate_merge",
                                       "at": moment.isoformat(),
                                       "survivor_id": str(survivor["id"]),
                                       "rule": f"token_jaccard>={MERGE_SIMILARITY}"})
                        session.execute(claims.update().where(claims.c.id == duplicate["id"]).values(
                            lifecycle_state="superseded", valid_to=moment,
                            correction_events=events, updated_at=moment,
                        ))
                        # A superseded duplicate must stop being served by retrieval.
                        session.execute(index_entries.delete().where(
                            index_entries.c.owner_id == owner_id,
                            index_entries.c.target_type == "self_claim",
                            index_entries.c.target_id == duplicate["id"],
                        ))
                        superseded += 1
                    summary = list(survivor["evidence_summary"] or [])
                    for duplicate in duplicates:
                        for entry in (duplicate["evidence_summary"] or []):
                            if entry not in summary:
                                summary.append(entry)
                    events = _correction_events(survivor)
                    events.append({"type": "merged_duplicates", "at": moment.isoformat(),
                                   "merged_claim_ids": merged_ids,
                                   "rule": f"token_jaccard>={MERGE_SIMILARITY}"})
                    session.execute(claims.update().where(claims.c.id == survivor["id"]).values(
                        evidence_summary=summary, correction_events=events, updated_at=moment,
                    ))
                    merged += len(duplicates)
        context.progress(100, "duplicate control applied")
        return {"merged": merged, "superseded": superseded,
                "suspected_items": suspected_items, "groups": groups_count, "scanned": len(rows)}

    return handler


def _claim_vectors(
    session: Any, tables: Mapping[str, sa.Table], owner_id: UUID,
    group: Sequence[Mapping[str, Any]], index_entries: sa.Table,
) -> dict[Any, Sequence[float]]:
    """Stored retrieval vectors for the claims in one bucket (PostgreSQL only)."""
    if session.get_bind().dialect.name != "postgresql":
        return {}
    rows = session.execute(sa.select(
        index_entries.c.target_id, index_entries.c.embedding,
    ).where(
        index_entries.c.owner_id == owner_id,
        index_entries.c.target_type == "self_claim",
        index_entries.c.embedding.is_not(None),
        index_entries.c.target_id.in_([row["id"] for row in group]),
    )).mappings().all()
    return {row["target_id"]: row["embedding"] for row in rows}