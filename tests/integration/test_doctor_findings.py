"""US10 doctor findings: corrupted asset, broken relation, low disk (T139)."""


def test_doctor_detects_low_disk_and_corrupt_asset():
    from personal_brain_domain.operations.doctor import check_components

    findings = check_components(disk_free_percent=4.0, assets_corrupted=("a1",), relations_broken=1)
    assert any("disk" in f for f in findings)
    assert any("corrupt" in f for f in findings)


def test_backup_retention_tiers_bounded():
    from personal_brain_domain.operations.backup import tier_expiration

    assert tier_expiration(tier="daily", age_days=6) == "active"
