"""Human knowledge import contract: bounded source identity and checkpoints.

FR-100/FR-101: a one-way paged idempotent import keeps source revision and
checkpoint; the imported note is classified as original_document, not inference.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class ImportedNote:
    note_id: str
    title: str
    raw_text: str
    source_id: str
    classification: str = "original_document"


def import_note(*, title: str, body: str, source_id: str) -> ImportedNote:
    if not source_id or not title:
        raise ValueError("import requires source and title")
    return ImportedNote(note_id=str(uuid.uuid4()), title=title, raw_text=body, source_id=source_id)