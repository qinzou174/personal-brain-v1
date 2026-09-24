"""US10 backup tier expiration and deleted-data disclosure (T140)."""

import pytest


def test_backup_tier_expiration_boundaries():
    from personal_brain_domain.operations.backup import tier_expiration

    assert tier_expiration(tier="daily", age_days=7) == "expired"
    assert tier_expiration(tier="weekly", age_days=28) == "expired"
    assert tier_expiration(tier="monthly", age_days=90) == "expired"


def test_deleted_data_disclosed_until_backup_purge():
    from personal_brain_domain.operations.backup import disclosure

    assert disclosure(backup_purge_due=False)["deleted_copies"] == "backup retains copy"
    assert disclosure(backup_purge_due=True)["deleted_copies"] == "backup purge due"
