"""Mixed-statement extraction orchestration as derived work.

FR-004..FR-007/FR-012..FR-019/ER-01/ER-02: extraction runs on immutable canonical
RawInput and produces distinguishable derived records with lineage; an extracted
interpretation never replaces original truth.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from personal_brain_domain.intake.lineage import DerivationIdentity
from personal_brain_domain.intake.service import CaptureOutcome
from personal_brain_domain.records.expenses import validate_money


@dataclass(frozen=True)
class ExtractedRecord:
    record_type: str  # expense | todo
    payload: object
    derivation_id: str


def extract_from_raw(
    *,
    raw_input_id: str,
    text: str,
    generator_version: str,
) -> list[ExtractedRecord]:
    """Extract structured records from a canonical raw statement.

    Every record is bound to the same RawInput via a new DerivationIdentity so
    reprocessing creates a new generation and never rewrites canonical input.
    """
    identity = DerivationIdentity(generator_kind="mixed_statement_extractor", generator_version=generator_version)
    records: list[ExtractedRecord] = []
    from personal_brain_domain.intake.service import ingest_mixed_statement

    outcome = ingest_mixed_statement(
        text=text,
        client_id="system",
        owner_timezone="Asia/Shanghai",
        idempotency_key=str(uuid.uuid4()),
    )
    for expense_id in outcome.expense_ids:
        records.append(ExtractedRecord(record_type="expense", payload={"expense_id": expense_id, "source_id": raw_input_id},
                                       derivation_id=str(identity.derivation_id)))
    for todo_id in outcome.todo_ids:
        records.append(ExtractedRecord(record_type="todo", payload={"todo_id": todo_id, "source_id": raw_input_id},
                                       derivation_id=str(identity.derivation_id)))
    return records
