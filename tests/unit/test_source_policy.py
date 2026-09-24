"""Source class/trust policy for memory and evidence (T031, FR-005/006/030)."""

import pytest


def test_source_class_trust_ordering_and_bounds():
    from personal_brain_domain.memory.source_policy import trust_level, validate_source_class

    assert trust_level("explicit_user_statement") > trust_level("observation")
    assert trust_level("observation") > trust_level("ai_extraction")
    assert trust_level("ai_extraction") > trust_level("ai_inference")
    with pytest.raises(ValueError):
        validate_source_class("random")


def test_source_class_in_evidence_explanation_uses_safe_label():
    from personal_brain_domain.memory.source_policy import source_class_label

    assert "explicit" in source_class_label("explicit_user_statement")
    assert source_class_label("ai_inference") == "inference"
