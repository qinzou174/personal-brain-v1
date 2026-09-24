"""US2 Scenario B: provenance and objective/subjective separation (T056)."""

import pytest


def test_raw_text_remains_and_derivation_is_distinguishable():
    from personal_brain_domain.intake.lineage import DerivationIdentity
    from personal_brain_domain.intake.reprocessing import reprocess

    raw_id = "raw-kyoto"
    first = reprocess(raw_input_id=raw_id, text="今天去了京都，午饭花了 4200 日元，人太多，不过晚上特别舒服。",
                      generator_version="v1")
    second = reprocess(raw_input_id=raw_id, text="今天去了京都，午饭花了 4200 日元，人太多，不过晚上特别舒服。",
                       generator_version="v1")
    # Reprocessing creates a distinguishable new derivation; the raw stays unchanged.
    assert first.derivation_id != second.derivation_id
    assert first.raw_input_id == raw_id == second.raw_input_id
    assert first.generator_version == second.generator_version


def test_experience_separated_from_objective_event():
    from personal_brain_domain.records.experiences import create_experience
    from personal_brain_domain.records.events import Event

    event = Event(event_id="e-1", event_type="travel", title="京都一日", objective_description="去了京都",
                  importance="normal", event_timezone="Asia/Tokyo", start_at=None, end_at=None)
    experience = create_experience(event_id=event.event_id, user_expression="人太多，不过晚上特别舒服",
                                   context="傍晚河边", source_id="raw-kyoto")
    assert experience.event_id == event.event_id
    assert experience.source_id == "raw-kyoto"
    # The experience is not a global preference by itself.
    assert experience.establishment == "candidate"


def test_provenance_explanation_reports_class_evidence_and_version():
    from personal_brain_domain.retrieval.provenance import explain_belief

    explanation = explain_belief(claim_id="c-1", source_class="ai_extraction", evidence_ids=("ev-1",),
                                 generator_version="v1", time_context="2026-09", confidence_basis="2 sources")
    assert "ai_extraction" in explanation["source_class"]
    assert explanation["generator_version"] == "v1"
    assert "ev-1" in explanation["evidence_ids"]
