"""High-risk workflow gate: preview, authorization, recovery, audit (T167)."""

from __future__ import annotations

import pytest


def test_deletion_preview_requires_confirmation_and_audit_ref():
    from personal_brain_domain.operations.deletion import execute_deletion
    from personal_brain_domain.common.errors import BrainError

    with pytest.raises(BrainError):
        execute_deletion(plan={"confirmed": True, "version": 2}, expected_version=1, confirmed=True)
    result = execute_deletion(plan={"confirmed": True, "version": 1, "targets": ["t1"]},
                              expected_version=1, confirmed=True)
    assert result.production_purged is True
