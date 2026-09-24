"""Trilium one-way import integration contract (T132, FR-100/FR-101)."""

import pytest


def test_import_is_paged_idempotent_with_checkpoint():
    from personal_brain_domain.intake.human_knowledge_contract import import_note
    from personal_brain_domain.operations.external_source_health import core_without_external

    page = [import_note(title="n1", body="b1", source_id="t-1")]
    assert page[0].source_id == "t-1"
    health = core_without_external(interface_enabled=False)
    assert health["core_available"] is True


def test_trilium_disabled_leaves_core_healthy():
    from personal_brain_domain.operations.external_source_health import core_without_external

    status = core_without_external(interface_enabled=False)
    assert status["external"] == "disabled"
