"""Secret filter applied before persistence sinks (T033, FR-045/FR-072)."""

import pytest


def test_secret_content_is_rejected_before_any_sink():
    from personal_brain_domain.intake.security_pipeline import check_before_persistence

    with pytest.raises(Exception) as caught:
        check_before_persistence(
            filename="config.txt",
            content_type="text/plain",
            content="token=sk-live-abcdefgh",
        )
    assert caught.value.code == "SECRET_REJECTED"
    assert "sk-live-abcdefgh" not in str(caught.value)


def test_ordinary_content_passes_all_sinks():
    from personal_brain_domain.intake.security_pipeline import check_before_persistence

    decision = check_before_persistence(
        filename="note.md", content_type="text/markdown", content="A normal thought."
    )
    assert decision.allowed is True
    assert decision.sinks == ("project", "document", "archive", "log", "search")
