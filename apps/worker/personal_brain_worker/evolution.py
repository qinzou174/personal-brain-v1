"""Scheduled evolution of candidate memories: promotion, retention, conflicts.

Δ3 wires the previously dead domain logic into the living loop:

- ``promote_candidates`` activates class-A rules and promotes class-B candidates
  that satisfy ``assess_b_promotion`` (>=3 sources, >=14 days, >=2 contexts, a
  direct user statement, no contradiction).  A contradiction anywhere under the
  same topic signature blocks promotion (FR-025/ER-02).
- ``retention_sweep`` applies policy-specific retention (FR-021/FR-022): class-B
  candidates expire after 90 unsupported days, established memories become
  historical after 180 days, class-A rules never age into expiry.  Nothing is
  deleted; each transition is recorded in ``correction_events``.
- ``conflict_scan`` records opposite-polarity claims under the same topic
  signature as a conflict plus an inbox review item (D4=a: no automatic
  confidence downgrade).

Topic signatures are a deliberately simple, deterministic heuristic (normalize
punctuation/whitespace, then remove negation markers), so the same text with and
without a negation compares as one topic with opposite polarity.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import sqlalchemy as sa

from personal_brain_domain.memory.evidence import PromotionEvidence, assess_b_promotion
from personal_brain_domain.memory.lifecycle import retention_transition
from personal_brain_domain.memory.polarity import is_negative, normalize_claim, topic_key
from personal_brain_domain.operations.retention import apply_retention

MAX_PROMOTION_SCAN = 500
MAX_RETENTION_SCAN = 1000
MAX_CONFLICT_PAIRS = 200


def _correction_events(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(event) for event in (row["correction_events"] or [])]


def make_promote_handler(
    session_factory: Any, tables: Mapping[str, sa.Table], *,
    now: Callable[[], datetime] | None = None,
) -> Callable[..., dict[str, Any]]:
    clock = now or (lambda: datetime.now(timezone.utc))

    def handler(job: dict[str, Any], context: Any) -> dict[str, Any]:
        owner_id = UUID(str(job["owner_id"]))
        moment = clock()
        claims_table, evidence_table, jobs_table = (
            tables["self_claims"], tables["evidence"], tables["jobs"],
        )
        activated = promoted = 0
        with session_factory.begin() as session:
            rows = session.execute(sa.select(claims_table).where(
                claims_table.c.owner_id == owner_id,
            ).limit(MAX_PROMOTION_SCAN)).mappings().all()

            # Class A: an explicit remembered rule is active without extra evidence.
            for row in rows:
                if row["policy_class"] != "A" or row["lifecycle_state"] != "candidate":
                    continue
                events = _correction_events(row)
                events.append({"type": "activated", "at": moment.isoformat(),
                               "rule": "class_a_explicit"})
                session.execute(claims_table.update().where(claims_table.c.id == row["id"]).values(
                    lifecycle_state="active", correction_events=events, updated_at=moment,
                ))
                activated += 1

            polarities: dict[str, set[bool]] = {}
            for row in rows:
                key = topic_key(row["claim"])
                if key:
                    polarities.setdefault(key, set()).add(is_negative(row["claim"]))

            groups: dict[tuple[str, bool], list[Mapping[str, Any]]] = {}
            for row in rows:
                if row["lifecycle_state"] != "candidate" or row["policy_class"] != "B":
                    continue
                groups.setdefault((topic_key(row["claim"]), is_negative(row["claim"])), []).append(row)

            for (key, _polarity), group in groups.items():
                if not key or len(polarities.get(key, set())) > 1:
                    continue  # a contradiction under this topic blocks promotion
                signals: list[PromotionEvidence] = [
                    PromotionEvidence(
                        source_id=row["source_id"], observed_at=row["created_at"],
                        context=row["context"] or "", direct_user_statement=True,
                    ) for row in group
                ]
                attached = session.execute(sa.select(evidence_table).where(
                    evidence_table.c.owner_id == owner_id,
                    evidence_table.c.target_type == "self_claim",
                    evidence_table.c.target_id.in_([row["id"] for row in group]),
                )).mappings().all()
                signals.extend(
                    PromotionEvidence(
                        source_id=row["source_id"], observed_at=row["observed_at"],
                        context=row["context"] or "",
                        direct_user_statement=row["source_type"] == "raw_input",
                        contradicts=row["stance"] == "contradicts",
                    ) for row in attached
                )
                if assess_b_promotion(signals) != "established":
                    continue
                survivor = sorted(group, key=lambda row: (row["created_at"], str(row["id"])))[0]
                unique_sources = {str(signal.source_id) for signal in signals}
                contexts = sorted({signal.context for signal in signals if signal.context})
                times = [signal.observed_at for signal in signals]
                span_days = round((max(times) - min(times)).total_seconds() / 86400.0, 2)
                events = _correction_events(survivor)
                events.append({"type": "promoted", "at": moment.isoformat(),
                               "evidence_count": len(unique_sources),
                               "contexts": contexts, "span_days": span_days})
                confidence_inputs = dict(survivor["confidence_inputs"] or {})
                confidence_inputs.update({
                    "evidence_count": len(unique_sources), "context_count": len(contexts),
                    "span_days": span_days, "assessed_at": moment.isoformat(),
                })
                session.execute(claims_table.update().where(
                    claims_table.c.id == survivor["id"],
                ).values(
                    establishment="established", lifecycle_state="active",
                    correction_events=events, confidence_inputs=confidence_inputs,
                    updated_at=moment,
                ))
                session.execute(jobs_table.insert().values(
                    id=uuid4(), owner_id=owner_id, client_id=None, job_type="index_self_claim",
                    payload_ref=f"self_claim:{survivor['id']}",
                    idempotency_key=uuid5(NAMESPACE_URL, f"brain-promote-index:{survivor['id']}"),
                    state="queued", priority=0, attempts=0, max_attempts=5,
                    available_at=moment, claim_token=0,
                ))
                promoted += 1
        context.progress(100, "candidate promotion assessed")
        return {"activated": activated, "promoted": promoted, "scanned": len(rows)}

    return handler


def make_retention_handler(
    session_factory: Any, tables: Mapping[str, sa.Table], *,
    now: Callable[[], datetime] | None = None,
) -> Callable[..., dict[str, Any]]:
    clock = now or (lambda: datetime.now(timezone.utc))

    def handler(job: dict[str, Any], context: Any) -> dict[str, Any]:
        owner_id = UUID(str(job["owner_id"]))
        moment = clock()
        claims_table, evidence_table = tables["self_claims"], tables["evidence"]
        index_entries = tables["search_index_entries"]
        expired = historical = archived_memories = 0
        with session_factory.begin() as session:
            rows = session.execute(sa.select(claims_table).where(
                claims_table.c.owner_id == owner_id,
                claims_table.c.lifecycle_state.in_(("candidate", "active")),
            ).limit(MAX_RETENTION_SCAN)).mappings().all()
            for row in rows:
                if row["lifecycle_state"] == "candidate":
                    current = "candidate"
                elif row["establishment"] == "established":
                    current = "established"
                else:
                    current = "active"
                last_supported = session.scalar(sa.select(sa.func.max(evidence_table.c.observed_at)).where(
                    evidence_table.c.owner_id == owner_id,
                    evidence_table.c.target_type == "self_claim",
                    evidence_table.c.target_id == row["id"],
                    evidence_table.c.stance == "supports",
                )) or row["created_at"]
                next_state = retention_transition(
                    current, last_supported_at=last_supported, now=moment,
                    policy_class=row["policy_class"],
                )
                if next_state == row["lifecycle_state"]:
                    continue
                events = _correction_events(row)
                events.append({"type": next_state, "at": moment.isoformat(),
                               "from": row["lifecycle_state"],
                               "last_supported_at": last_supported.isoformat()})
                session.execute(claims_table.update().where(claims_table.c.id == row["id"]).values(
                    lifecycle_state=next_state, correction_events=events, updated_at=moment,
                ))
                if next_state == "expired":
                    # An unsupported candidate must stop being served by retrieval.
                    session.execute(index_entries.delete().where(
                        index_entries.c.owner_id == owner_id,
                        index_entries.c.target_type == "self_claim",
                        index_entries.c.target_id == row["id"],
                    ))
                    expired += 1
                elif next_state == "historical":
                    historical += 1

            if "memories" in tables:
                memories = tables["memories"]
                memory_rows = session.execute(sa.select(memories).where(
                    memories.c.owner_id == owner_id,
                    memories.c.lifecycle_state.in_(("candidate", "temporary")),
                ).limit(MAX_RETENTION_SCAN)).mappings().all()
                for row in memory_rows:
                    age_days = (moment - row["created_at"]).total_seconds() / 86400.0
                    outcome = apply_retention(kind=row["lifecycle_state"], age_days=age_days)
                    if outcome.action not in {"archive", "expire"}:
                        continue
                    session.execute(memories.update().where(memories.c.id == row["id"]).values(
                        lifecycle_state="archived" if outcome.action == "archive" else "expired",
                    ))
                    archived_memories += 1
        context.progress(100, "policy-specific retention applied")
        return {"expired": expired, "historical": historical,
                "archived_memories": archived_memories, "scanned": len(rows)}

    return handler


def make_conflict_handler(
    session_factory: Any, tables: Mapping[str, sa.Table], *,
    now: Callable[[], datetime] | None = None,
) -> Callable[..., dict[str, Any]]:
    clock = now or (lambda: datetime.now(timezone.utc))

    def handler(job: dict[str, Any], context: Any) -> dict[str, Any]:
        owner_id = UUID(str(job["owner_id"]))
        moment = clock()
        claims_table, conflicts_table = tables["self_claims"], tables["conflicts"]
        items_table, jobs_table = tables["review_inbox_items"], tables["jobs"]
        created = 0
        with session_factory.begin() as session:
            rows = session.execute(sa.select(claims_table).where(
                claims_table.c.owner_id == owner_id,
                claims_table.c.lifecycle_state.in_(("candidate", "active", "historical")),
            ).limit(MAX_PROMOTION_SCAN)).mappings().all()
            established = [row for row in rows if (
                row["establishment"] == "established"
                or (row["policy_class"] == "A" and row["lifecycle_state"] == "active")
            )]
            candidates = [row for row in rows if row["lifecycle_state"] == "candidate"]
            established_topics: dict[str, list[Mapping[str, Any]]] = {}
            for row in established:
                established_topics.setdefault(topic_key(row["claim"]), []).append(row)
            open_items = session.execute(sa.select(items_table.c.subject_refs).where(
                items_table.c.owner_id == owner_id,
                items_table.c.item_type == "conflict",
                items_table.c.state.in_(("open", "deferred")),
            )).mappings().all()
            known_pairs = {frozenset(str(ref) for ref in (row["subject_refs"] or []))
                           for row in open_items}
            # A verdict the owner already gave is final: adjudicated conflicts
            # (resolved/tolerated) must never regenerate the same item, or the
            # owner sees the same contradiction every single day.
            if "conflicts" in tables:
                adjudicated = session.execute(sa.select(conflicts_table.c.participants).where(
                    conflicts_table.c.owner_id == owner_id,
                    conflicts_table.c.state != "open",
                )).mappings().all()
                known_pairs.update(
                    frozenset(str(ref) for ref in (row["participants"] or []))
                    for row in adjudicated
                )
            # One conflict item per contradicting topic: ten opposite notes under
            # the same topic are one thing for the owner to review, not ten.
            by_id = {str(row["id"]): row for row in rows}
            conflicted_topics = set()
            for item in open_items:
                for ref in (item["subject_refs"] or []):
                    claim_row = by_id.get(str(ref))
                    if claim_row is not None:
                        conflicted_topics.add(topic_key(claim_row["claim"]))
            for candidate in candidates:
                if created >= MAX_CONFLICT_PAIRS:
                    break
                key = topic_key(candidate["claim"])
                if not key or key in conflicted_topics:
                    continue
                for other in established_topics.get(key, []):
                    if other["id"] == candidate["id"]:
                        continue
                    if is_negative(other["claim"]) == is_negative(candidate["claim"]):
                        continue
                    pair = frozenset({str(other["id"]), str(candidate["id"])})
                    if pair in known_pairs:
                        continue
                    session.execute(conflicts_table.insert().values(
                        id=uuid4(), owner_id=owner_id,
                        participants=sorted(pair), conflict_type="polarity",
                        detected_at=moment,
                        evidence=[{"established_claim": other["claim"],
                                   "candidate_claim": candidate["claim"],
                                   "source_id": str(candidate["source_id"])}],
                        state="open", resolution=None, resolver=None,
                    ))
                    item_id = uuid4()
                    session.execute(items_table.insert().values(
                        id=item_id, owner_id=owner_id, item_type="conflict",
                        subject_refs=sorted(pair),
                        proposal={"kind": "polarity_conflict",
                                  "established_claim": other["claim"],
                                  "candidate_claim": candidate["claim"]},
                        risk="ordinary",
                        evidence=[{"candidate_source_id": str(candidate["source_id"])}],
                        state="open", resolver_id=None, resolved_at=None,
                        expires_at=None, expected_version=1,
                    ))
                    session.execute(jobs_table.insert().values(
                        id=uuid4(), owner_id=owner_id, client_id=None, job_type="notify_review",
                        payload_ref=f"review_item:{item_id}",
                        idempotency_key=uuid5(NAMESPACE_URL, f"brain-conflict-review:{item_id}"),
                        state="queued", priority=0, attempts=0, max_attempts=5,
                        available_at=moment, claim_token=0,
                    ))
                    known_pairs.add(pair)
                    conflicted_topics.add(key)
                    created += 1
        context.progress(100, "conflict scan committed")
        return {"conflicts": created, "candidates_scanned": len(candidates)}

    return handler