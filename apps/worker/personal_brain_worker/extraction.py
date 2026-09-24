"""LLM extraction of one raw input into derived content plus B-class candidates.

Δ2 / D2(b): the previously mis-wired ``extract_raw_input`` job (it only indexed)
now performs a real bounded model extraction.  The model output is parsed into a
strict structure and persisted as ``derived_contents`` (kind=description) plus,
per candidate, a class-B ``self_claims`` candidate with an evidence row and
lineage edges.  The raw input stays canonical; nothing here becomes an
established fact on its own.

Failure semantics stay honest and bounded:
- no provider/gateway  -> completed with ``skipped=provider_unavailable`` (no
  fabricated derivation);
- daily budget reached -> completed with ``skipped=daily_quota_exceeded``
  (rules-only degradation, FR-084 does not apply because nothing was attempted);
- malformed model output -> retryable ``BRAIN_UNAVAILABLE`` so the durable job
  retries inside its attempt budget instead of claiming success.
"""

from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Mapping
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import sqlalchemy as sa

from personal_brain_domain.common.errors import BrainError
from personal_brain_domain.security.secret_filter import detect_secret
from personal_brain_infra.models.gateway import ModelGateway, ProviderCallBudget
from personal_brain_infra.storage.base import StorageBackend
from personal_brain_worker.claim_dedupe import find_duplicate
from personal_brain_worker.llm_budget import quota_exceeded
from personal_brain_worker.runtime import JobExecutionError

EXTRACTION_VERSION = "extract-v1"
MAX_RAW_CHARS = 6000
MAX_CANDIDATES = 5

# Must mirror the DB check constraint self_category_allowed (0004) so a model
# category can never reach an INSERT that would fail with an IntegrityError.
SELF_CLAIM_CATEGORIES = frozenset({
    "preference", "aesthetic", "value", "working_style",
    "communication_style", "interest", "habit", "goal", "philosophy",
})
CATEGORY_ALIASES = {
    "偏好": "preference", "审美": "aesthetic", "价值观": "value", "价值": "value",
    "工作方式": "working_style", "工作风格": "working_style",
    "沟通方式": "communication_style", "沟通风格": "communication_style",
    "兴趣": "interest", "爱好": "interest", "习惯": "habit", "目标": "goal",
    "哲学": "philosophy", "人生哲学": "philosophy",
}
_CONFIDENCE_LEVELS = frozenset({"low", "medium", "high"})

_EXTRACTION_INSTRUCTION = (
    "你是个人知识库的结构化抽取器。只根据给出的记录文本抽取，不得编造或补充。"
    "输出严格 JSON（不要解释、不要代码块标记），结构为："
    '{"summary": "一句话中性复述记录内容", "candidates": ['
    '{"category": "<preference|aesthetic|value|working_style|communication_style|interest|habit|goal|philosophy>", '
    '"claim": "关于用户本人的偏好/习惯/兴趣/目标/价值观/风格的陈述", '
    '"confidence": "<low|medium|high>", "quote": "记录中的原始依据片段"}]}。'
    "规则：candidates 只包含关于用户本人的偏好类陈述；金额、待办、日程、地点事实不要输出；"
    f"最多 {MAX_CANDIDATES} 条；没有则输出空数组。"
)


def build_extraction_request(text: str) -> dict[str, Any]:
    clipped = text[:MAX_RAW_CHARS]
    return {
        "prompt": f"{_EXTRACTION_INSTRUCTION}\n\n<记录>\n{clipped}\n</记录>",
        "max_tokens": 1600,
        "thinking": {"type": "disabled"},
    }


def _extract_json_object(text: str) -> dict[str, Any]:
    if not isinstance(text, str):
        raise ValueError("model output must be text")
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object in model output")
    depth = 0
    for position in range(start, len(text)):
        character = text[position]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(text[start:position + 1])
                except json.JSONDecodeError as error:
                    raise ValueError("model output is not valid JSON") from error
                if not isinstance(parsed, dict):
                    raise ValueError("model output must be a JSON object")
                return parsed
    raise ValueError("unbalanced JSON in model output")


def parse_extraction_output(text: str) -> dict[str, Any]:
    """Parse and validate a model extraction into ``summary`` + ``candidates``.

    Invalid candidates are dropped (counted in ``dropped``) instead of failing the
    whole extraction; a missing summary or unusable JSON raises ``ValueError``.
    """
    parsed = _extract_json_object(text)
    summary = parsed.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("model output has no usable summary")
    raw_candidates = parsed.get("candidates", [])
    if not isinstance(raw_candidates, list):
        raise ValueError("model output candidates must be a list")
    candidates: list[dict[str, str]] = []
    dropped = 0
    for item in raw_candidates[:MAX_CANDIDATES + 5]:
        if not isinstance(item, dict):
            dropped += 1
            continue
        category = str(item.get("category", "")).strip().lower()
        category = CATEGORY_ALIASES.get(category, category)
        claim = str(item.get("claim", "")).strip()
        if category not in SELF_CLAIM_CATEGORIES or not claim:
            dropped += 1
            continue
        confidence = str(item.get("confidence", "")).strip().lower()
        if confidence not in _CONFIDENCE_LEVELS:
            confidence = "low"
        candidates.append({
            "category": category, "claim": claim[:500], "confidence": confidence,
            "quote": str(item.get("quote", "")).strip()[:200],
        })
        if len(candidates) >= MAX_CANDIDATES:
            break
    return {"summary": summary.strip()[:2000], "candidates": candidates, "dropped": dropped}


def make_extract_handler(
    session_factory: Any, tables: Mapping[str, sa.Table], storage: StorageBackend | None,
    gateway: ModelGateway | None, *, quota: int = 200,
    timezone_name: str = "Asia/Shanghai", now: Callable[[], datetime] | None = None,
) -> Callable[..., dict[str, Any]]:
    clock = now or (lambda: datetime.now(timezone.utc))

    def handler(job: dict[str, Any], context: Any) -> dict[str, Any]:
        # Tables are resolved per execution so the registry can be built (and
        # unit-tested) before the physical schema is reflected.
        raws, intakes = tables["raw_inputs"], tables["intake_requests"]
        derived, edges = tables["derived_contents"], tables["derivation_edges"]
        claims, evidence, jobs = tables["self_claims"], tables["evidence"], tables["jobs"]
        try:
            target_type, raw_id_text = job["payload_ref"].split(":", 1)
            if target_type != "raw_input":
                raise ValueError
            raw_id, owner_id = UUID(raw_id_text), UUID(str(job["owner_id"]))
        except (ValueError, AttributeError) as error:
            raise JobExecutionError("VALIDATION_FAILED", retryable=False) from error

        with session_factory() as session:
            row = session.execute(sa.select(raws, intakes.c.requested_scope).join(
                intakes, intakes.c.id == raws.c.intake_request_id,
            ).where(
                raws.c.id == raw_id, raws.c.owner_id == owner_id,
                raws.c.lifecycle_state == "active",
            )).mappings().one_or_none()
            existing = session.execute(sa.select(derived.c.id).where(
                derived.c.owner_id == owner_id, derived.c.target_type == "raw_input",
                derived.c.target_id == raw_id, derived.c.kind == "description",
                derived.c.derivation_version == EXTRACTION_VERSION,
            )).scalar()
        if row is None or not row["content_text"]:
            raise JobExecutionError("NOT_FOUND", retryable=False)
        # Decision (b), 2026-09-25: a secret-like note keeps its canonical raw text
        # locally but is never sent to a model provider. The skip is declared (no
        # dead letter, no retry loop) and no derived content is fabricated.
        if detect_secret(
            filename="extraction-input.txt", content_type="text/plain",
            content=row["content_text"],
        ).matched:
            return {"extracted": 0, "dropped": 0, "skipped": "secret_like_content"}
        if existing is not None:
            return {"extracted": 0, "dropped": 0, "skipped": "already_extracted",
                    "derived_id": str(existing)}

        if not isinstance(gateway, ModelGateway) or gateway.provider is None or gateway.card is None:
            return {"extracted": 0, "dropped": 0, "skipped": "provider_unavailable"}
        moment = clock()
        with session_factory() as session:
            over_budget = quota_exceeded(
                session, jobs, owner_id=owner_id, now_utc=moment,
                timezone_name=timezone_name, quota=quota,
            )
        if over_budget:
            return {"extracted": 0, "skipped": "daily_quota_exceeded", "quota": quota}

        context.progress(20, "bounded extraction call acquired")
        try:
            result = gateway.execute(
                build_extraction_request(row["content_text"]),
                {"target_type": "raw_input", "payload_ref": f"raw_input:{raw_id}",
                 "kind": "extract_candidates"},
                sensitivity=row["sensitivity"], budget=ProviderCallBudget(max_calls=1),
            )
        except BrainError as error:
            if error.code == "SECRET_REJECTED":
                # Defence in depth: the gateway re-checks the encoded request, so
                # a match here is still a declared skip, never a dead letter.
                return {"extracted": 0, "dropped": 0, "skipped": "secret_like_content"}
            raise JobExecutionError(
                error.code, retryable=error.code in {"BRAIN_UNAVAILABLE", "DEPENDENCY_CONFLICT"},
            ) from error
        try:
            parsed = parse_extraction_output(result.get("text", ""))
        except ValueError as error:
            raise JobExecutionError("BRAIN_UNAVAILABLE", retryable=True) from error
        context.progress(60, "model output parsed")

        payload = {
            "summary": parsed["summary"], "candidates": parsed["candidates"],
            "dropped": parsed["dropped"], "model": result.get("model"),
            "extraction_version": EXTRACTION_VERSION,
            "raw_input_id": str(raw_id),
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        payload_ref = None
        if storage is not None:
            stored = storage.store_atomic(
                io.BytesIO(encoded), expected_sha256=hashlib.sha256(encoded).hexdigest(),
                expected_size=len(encoded), content_type="application/json",
            )
            payload_ref = stored.storage_key

        derived_id = uuid4()
        claim_context = f"{row['source_channel']}:{row['requested_scope']}"[:256]
        # D2: load the owner's live claims so a duplicate candidate never becomes a
        # second row; its evidence attaches to the claim the owner already has.
        pool: list[dict[str, Any]] = []
        if parsed["candidates"]:
            with session_factory() as session:
                pool = [dict(claim_row) for claim_row in session.execute(sa.select(claims).where(
                    claims.c.owner_id == owner_id,
                    claims.c.category.in_({candidate["category"] for candidate in parsed["candidates"]}),
                    claims.c.lifecycle_state.in_(("candidate", "active", "historical")),
                )).mappings().all()]
        merged = 0
        with session_factory.begin() as session:
            session.execute(derived.insert().values(
                id=derived_id, owner_id=owner_id, target_type="raw_input", target_id=raw_id,
                kind="description", derivation_version=EXTRACTION_VERSION,
                generator_kind="model", generator_version=EXTRACTION_VERSION,
                derived_at=moment, confidence="model_generated",
                confidence_inputs={"model": result.get("model"), "candidate_count": len(parsed["candidates"]),
                                   "dropped": parsed["dropped"]},
                payload_ref=payload_ref, state="active", sensitivity=row["sensitivity"],
                information_class="ai_extraction", canonicality="derived",
                source_kind="ai_extraction", source_id=raw_id, valid_from=moment,
                valid_to=None, lifecycle_state="active", deleted_at=None,
            ))
            session.execute(edges.insert().values(
                id=uuid4(), owner_id=owner_id, source_type="raw_input", source_id=raw_id,
                derived_type="derived_content", derived_id=derived_id, role="extracted_from",
                contribution_weight=1, generator_version=EXTRACTION_VERSION,
            ))
            for candidate in parsed["candidates"]:
                match = find_duplicate(
                    candidate["claim"],
                    [claim_row for claim_row in pool
                     if claim_row["category"] == candidate["category"]],
                )
                if match is not None and match[1] == "duplicate":
                    existing_row = match[0]
                    session.execute(evidence.insert().values(
                        id=uuid4(), owner_id=owner_id, target_type="self_claim",
                        target_id=existing_row["id"], source_type="raw_input", source_id=raw_id,
                        stance="supports", source_trust="ai_extraction", observed_at=moment,
                        context=claim_context, contribution=Decimal("0.3"), lifecycle_state="active",
                    ))
                    session.execute(edges.insert().values(
                        id=uuid4(), owner_id=owner_id, source_type="raw_input", source_id=raw_id,
                        derived_type="self_claim", derived_id=existing_row["id"], role="inferred_from",
                        contribution_weight=Decimal("0.3"), generator_version=EXTRACTION_VERSION,
                    ))
                    summary = list(existing_row.get("evidence_summary") or [])
                    summary.append({"raw_input": str(raw_id), "derived_id": str(derived_id),
                                    "quote": candidate["quote"], "merged_by": "dedupe_v1"})
                    events = [dict(event) for event in (existing_row.get("correction_events") or [])]
                    events.append({"type": "duplicate_candidate_merged", "at": moment.isoformat(),
                                   "raw_input": str(raw_id),
                                   "rule": "normalized_or_token_jaccard>=0.75"})
                    session.execute(claims.update().where(
                        claims.c.id == existing_row["id"],
                    ).values(evidence_summary=summary, correction_events=events, updated_at=moment))
                    existing_row["evidence_summary"] = summary
                    merged += 1
                    continue
                claim_id = uuid4()
                session.execute(claims.insert().values(
                    id=claim_id, owner_id=owner_id, category=candidate["category"],
                    claim=candidate["claim"], policy_class="B", lifecycle_state="candidate",
                    establishment="candidate", review="none", correction_events=[],
                    confidence_inputs={"model": result.get("model"),
                                       "confidence": candidate["confidence"],
                                       "extraction_version": EXTRACTION_VERSION},
                    evidence_summary=[{"raw_input": str(raw_id), "derived_id": str(derived_id),
                                       "quote": candidate["quote"]}],
                    valid_from=moment, valid_to=None, context=claim_context, exceptions=[],
                    confirmation_identity=None, confirmation_time=None, source_id=raw_id,
                ))
                session.execute(evidence.insert().values(
                    id=uuid4(), owner_id=owner_id, target_type="self_claim", target_id=claim_id,
                    source_type="raw_input", source_id=raw_id, stance="supports",
                    source_trust="ai_extraction", observed_at=moment, context=claim_context,
                    contribution=Decimal("0.3"), lifecycle_state="active",
                ))
                session.execute(edges.insert().values(
                    id=uuid4(), owner_id=owner_id, source_type="raw_input", source_id=raw_id,
                    derived_type="self_claim", derived_id=claim_id, role="inferred_from",
                    contribution_weight=Decimal("0.3"), generator_version=EXTRACTION_VERSION,
                ))
                session.execute(jobs.insert().values(
                    id=uuid4(), owner_id=owner_id, client_id=None, job_type="index_self_claim",
                    payload_ref=f"self_claim:{claim_id}",
                    idempotency_key=uuid5(NAMESPACE_URL, f"brain-extract-index:{claim_id}"),
                    state="queued", priority=0, attempts=0, max_attempts=5,
                    available_at=moment, claim_token=0,
                ))
                # Later candidates in the same output must see this row too.
                pool.append({"id": claim_id, "category": candidate["category"],
                             "claim": candidate["claim"], "evidence_summary": [],
                             "correction_events": []})
        context.progress(100, "extraction committed")
        return {"extracted": len(parsed["candidates"]) - merged, "merged": merged,
                "dropped": parsed["dropped"], "derived_id": str(derived_id)}

    return handler