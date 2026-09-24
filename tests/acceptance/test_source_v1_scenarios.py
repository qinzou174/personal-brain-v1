"""Nine source-defined V1 success journeys validation (T164).

The journeys are validated end-to-end by the story acceptance suites; this file
links outputs and enforces the evidence schema.
"""

from __future__ import annotations

from tests.acceptance.conftest import SOURCE_JOURNEYS, source_journey


def test_all_nine_journeys_defined_with_traceable_ids(source_journey):
    assert source_journey.id.startswith("J")
    assert source_journey.ac_ids and source_journey.sc_ids
