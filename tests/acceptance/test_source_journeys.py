"""Source §103–111 journeys exist before feature implementation."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from tests.acceptance.conftest import SOURCE_JOURNEYS, _declared_ids


def test_nine_journey_ids_and_source_sections_are_complete():
    assert [case.id for case in SOURCE_JOURNEYS] == [f"J{index:02d}" for index in range(1, 10)]
    assert [case.source_section for case in SOURCE_JOURNEYS] == list(range(103, 112))
    assert all("SC-001" in case.sc_ids and case.ac_ids for case in SOURCE_JOURNEYS)
    ac_ids, sc_ids = _declared_ids()
    assert all(set(case.ac_ids) <= ac_ids and set(case.sc_ids) <= sc_ids for case in SOURCE_JOURNEYS)


def test_evidence_schema_rejects_shallow_success(evidence_type):
    base = dict(
        journey_id="J01", ac_ids=("AC-07",), sc_ids=("SC-001",),
        environment_id="synthetic-local", implementation_revision="rev-1",
        precondition="fixture loaded", action="resume project", observed_outcome="recorded",
        status="passed", reviewer_decision="approved", observed_at=datetime.now(timezone.utc),
    )
    for refs in ((), ("mock:chat",), ("http-status:200",)):
        with pytest.raises(ValidationError):
            evidence_type(**(base | {"authoritative_refs": refs}))


def test_source_journey_end_to_end(source_journey, journey_runner, evidence_type):
    observed = journey_runner.run(source_journey)
    evidence = evidence_type.model_validate(observed)
    assert evidence.journey_id == source_journey.id
    assert set(source_journey.ac_ids) <= set(evidence.ac_ids)
    assert set(source_journey.sc_ids) <= set(evidence.sc_ids)
    assert evidence.status == "passed"
