"""US2 lineage integration: orphan, source deletion, version replay, authorization (T057)."""

import pytest


def test_lineage_orphan_on_last_source_loss():
    from personal_brain_domain.intake.lineage import recalculate_derivation_state

    assert recalculate_derivation_state(current_state="active", live_source_ids=[]) == "orphaned"


def test_source_deletion_orphans_but_keeps_history():
    from personal_brain_domain.intake.lineage import next_derivation_version

    v1 = next_derivation_version(current_version=None, generator_version="g1")
    v2 = next_derivation_version(current_version=v1, generator_version="g1")
    assert v1 != v2
    assert v2.startswith("g1:")


def test_version_replay_never_rewrites_canonical():
    from personal_brain_domain.intake.reprocessing import reprocess

    first = reprocess(raw_input_id="raw-x", text="原文", generator_version="g2")
    replay = reprocess(raw_input_id="raw-x", text="原文", generator_version="g2")
    assert first.derivation_id != replay.derivation_id
    assert first.raw_text == "原文" and replay.raw_text == "原文"


def test_derived_access_requires_source_authorization():
    from personal_brain_domain.intake.lineage import derive_access_boundary

    boundary = derive_access_boundary([
        {"scopes": {"finance"}, "sensitivity": "private"},
        {"scopes": {"finance", "personal"}, "sensitivity": "personal"},
    ])
    assert boundary.scopes == {"finance"}
    assert boundary.sensitivity == "private"
