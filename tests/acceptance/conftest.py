"""Nine source-defined journeys and an evidence gate for later end-to-end suites.

AC/SC IDs are checked against traceability.md, and a passing claim requires
authoritative observed evidence, not just a test process exiting successfully.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Literal

import pytest
from pydantic import BaseModel, Field, model_validator


class JourneyCase(BaseModel):
    id: str
    source_section: int
    title: str
    ac_ids: tuple[str, ...]
    sc_ids: tuple[str, ...]


SOURCE_JOURNEYS = (
    JourneyCase(id="J01", source_section=103, title="cross-account project recovery", ac_ids=("AC-07", "AC-08"), sc_ids=("SC-001", "SC-004", "SC-005")),
    JourneyCase(id="J02", source_section=104, title="cross-client life records", ac_ids=("AC-01", "AC-02", "AC-03"), sc_ids=("SC-001", "SC-003", "SC-008")),
    JourneyCase(id="J03", source_section=105, title="document and preference evidence", ac_ids=("AC-05", "AC-06"), sc_ids=("SC-001", "SC-002", "SC-012")),
    JourneyCase(id="J04", source_section=106, title="A/B/C memory policy", ac_ids=("AC-04", "AC-05"), sc_ids=("SC-001", "SC-012")),
    JourneyCase(id="J05", source_section=107, title="module staleness", ac_ids=("AC-08",), sc_ids=("SC-001", "SC-005")),
    JourneyCase(id="J06", source_section=108, title="context loss recovery", ac_ids=("AC-07", "AC-09"), sc_ids=("SC-001", "SC-004", "SC-011")),
    JourneyCase(id="J07", source_section=109, title="permission denial", ac_ids=("AC-10", "AC-12"), sc_ids=("SC-001", "SC-006", "SC-015")),
    JourneyCase(id="J08", source_section=110, title="secret exclusion", ac_ids=("AC-11",), sc_ids=("SC-001", "SC-007")),
    JourneyCase(id="J09", source_section=111, title="offline honesty", ac_ids=("AC-15",), sc_ids=("SC-001", "SC-008")),
)


class AcceptanceEvidence(BaseModel):
    journey_id: str
    ac_ids: tuple[str, ...]
    sc_ids: tuple[str, ...]
    environment_id: str = Field(min_length=1)
    implementation_revision: str = Field(min_length=1)
    precondition: str = Field(min_length=1)
    action: str = Field(min_length=1)
    observed_outcome: str = Field(min_length=1)
    authoritative_refs: tuple[str, ...]
    failures: tuple[str, ...] = ()
    status: Literal["pending", "passed", "failed"]
    reviewer_decision: str | None = None
    observed_at: datetime

    @model_validator(mode="after")
    def require_authoritative_pass(self):
        if self.observed_at.tzinfo is None:
            raise ValueError("evidence time must include timezone")
        if self.status == "passed":
            if not self.authoritative_refs or self.failures or not self.reviewer_decision:
                raise ValueError("passed journey requires authoritative refs and reviewer decision")
            if any(ref.startswith(("mock:", "placeholder:", "http-status:")) for ref in self.authoritative_refs):
                raise ValueError("mock or shallow availability evidence cannot prove acceptance")
        return self


def _declared_ids() -> tuple[set[str], set[str]]:
    traceability = Path(__file__).parents[2] / "specs" / "001-personal-brain-v1" / "traceability.md"
    text = traceability.read_text(encoding="utf-8")
    ac_ids = set(re.findall(r"^\| (AC-\d{2}) \|", text, flags=re.MULTILINE))
    sc_ids = set(re.findall(r"^\| (SC-\d{3}) \|", text, flags=re.MULTILINE))
    return ac_ids, sc_ids


@pytest.fixture(params=SOURCE_JOURNEYS, ids=[case.id for case in SOURCE_JOURNEYS])
def source_journey(request) -> JourneyCase:
    ac_ids, sc_ids = _declared_ids()
    case = request.param
    assert set(case.ac_ids) <= ac_ids, f"unknown AC mapping for {case.id}"
    assert set(case.sc_ids) <= sc_ids, f"unknown SC mapping for {case.id}"
    return case


@pytest.fixture
def evidence_type():
    return AcceptanceEvidence


@pytest.fixture
def journey_runner():
    # Each story phase will supply the synthetic end-to-end runtime; never use a
    # mock-only answer as proof that a journey passed.
    from tests.acceptance.runtime import build_synthetic_runtime

    return build_synthetic_runtime()
