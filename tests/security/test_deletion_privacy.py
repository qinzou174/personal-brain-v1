"""US8 backup-retention disclosure and post-delete non-disclosure (T114)."""

import pytest


def test_deletion_discloses_backup_retention():
    from personal_brain_domain.operations.deletion_plan import backup_implications

    implications = backup_implications(backup_tiers=("daily", "weekly"), purge_due=True)
    assert implications["production_purged"] is True
    assert implications["backup_purge_due"] is True


def test_post_delete_audit_contains_no_deleted_body():
    from personal_brain_domain.security.audit import audit_repr, build_audit_event

    marker = "deleted-private-body"
    event = build_audit_event(client_id="c", action="delete", outcome="completed", duration_ms=3,
                              correlation_id="corr", details={"target": "note-1", "body": marker})
    assert marker not in audit_repr(event)
