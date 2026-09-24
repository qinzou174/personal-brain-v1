"""US4 source-authority and stale-warning integration (T073)."""

import pytest


def test_stale_module_warns_and_fresh_module_does_not():
    from personal_brain_domain.projects.modules import freshness_for, stale_warnings

    stale = freshness_for(evidence={"fresh": False})
    fresh = freshness_for(evidence={"fresh": True})
    assert stale_warnings(module="brain-core", freshness=stale) is not None
    assert stale_warnings(module="docs", freshness=fresh) is None


def test_revision_evidence_binds_module_state():
    from personal_brain_domain.projects.modules import freshness_from_revision

    assert freshness_from_revision(indexed_revision="abc", current_revision="abc") == "fresh"
    assert freshness_from_revision(indexed_revision="abc", current_revision="def") == "stale"
    assert freshness_from_revision(indexed_revision=None, current_revision=None) == "unknown"
