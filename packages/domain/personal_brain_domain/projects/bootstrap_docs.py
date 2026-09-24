"""Legacy project-document extraction with preserved sources/confidence.

FR-046: legacy project docs are one-way imported with their original source and
confidence retained; extraction never rewrites the source document.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LegacyExtraction:
    source_document: str
    content: str
    source_confidence: str = "original_document"
    preserved_source: bool = True


def extract_from_legacy_document(*, source_document: str, content: str) -> LegacyExtraction:
    if not source_document:
        raise ValueError("source document identity is required")
    return LegacyExtraction(source_document=source_document, content=content, source_confidence="original_document")