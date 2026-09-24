"""US12 Scenario N: source-preserving import, removable human interface (T130)."""

import pytest


def test_import_preserves_source_and_classification():
    from personal_brain_domain.intake.human_knowledge_contract import import_note

    imported = import_note(title="会议记录", body="今天讨论了 V1 验收", source_id="trilium-note-1")
    assert imported.source_id == "trilium-note-1"
    assert imported.classification == "original_document"
    assert imported.raw_text == "今天讨论了 V1 验收"


def test_core_works_with_interface_disabled():
    from personal_brain_domain.operations.external_source_health import core_without_external

    status = core_without_external(interface_enabled=False)
    assert status["core_available"] is True
    assert status["external"] == "disabled"
