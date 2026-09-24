"""Source class and trust ordering for memory and evidence.

FR-005/FR-006/FR-030: every stored item identifies its information class and
source class; provenance answers must explain the source class behind a belief.
Trust is strictly ordered so inference can never outrank explicit statements.
"""

from __future__ import annotations

_VALID_CLASSES = frozenset({
    "explicit_user_statement", "original_document", "system_fact",
    "observation", "ai_extraction", "ai_inference",
})

_TRUST_ORDER = {
    "system_fact": 100,
    "explicit_user_statement": 90,
    "original_document": 70,
    "observation": 50,
    "ai_extraction": 30,
    "ai_inference": 10,
}

_LABELS = {
    "system_fact": "system fact",
    "explicit_user_statement": "explicit user statement",
    "original_document": "original document",
    "observation": "observed",
    "ai_extraction": "extracted",
    "ai_inference": "inference",
}


def validate_source_class(value: str) -> str:
    if value not in _VALID_CLASSES:
        raise ValueError("unknown source class")
    return value


def trust_level(source_class: str) -> int:
    """Higher means the Brain may treat the statement as more reliable."""
    validate_source_class(source_class)
    return _TRUST_ORDER[source_class]


def source_class_label(source_class: str) -> str:
    validate_source_class(source_class)
    return _LABELS[source_class]
