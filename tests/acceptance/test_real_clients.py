"""Real-client matrix: TRAE/Cursor/ChatGPT connection evidence.

Mocks are not substitutes; blocked results stay EXTERNAL_VERIFICATION_PENDING.
"""

from __future__ import annotations

import pytest


def test_client_matrix_records_pending_status():
    from pathlib import Path

    matrix = Path(__file__).resolve().parents[2] / "docs" / "acceptance" / "client-matrix.md"
    assert "EXTERNAL_VERIFICATION_PENDING" in matrix.read_text(encoding="utf-8")


@pytest.mark.skip(reason="real TRAE/Cursor/ChatGPT accounts are not available in this environment")
def test_real_trae_cross_client_read_write():
    raise AssertionError("real-client acceptance must not be mocked")


@pytest.mark.skip(reason="real client revocation evidence requires live accounts")
def test_real_revocation():
    raise AssertionError("real-client revocation must not be mocked")


@pytest.mark.skip(reason="no-history resume requires a real fresh session")
def test_real_no_history_resume():
    raise AssertionError("real no-history resume must not be mocked")
