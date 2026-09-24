"""DB/job readiness preflight and reconnect (T040, FR-083/FR-092)."""

import pytest


def test_preflight_reports_components_without_connecting():
    from personal_brain_server.bootstrap.preflight import preflight_report

    report = preflight_report(database="unchecked", worker="unchecked", storage="unchecked")
    assert report["database"] == "unchecked"
    assert report["worker"] == "unchecked"
    assert report["storage"] == "unchecked"


def test_preflight_never_claims_ready_without_evidence():
    from personal_brain_server.bootstrap.preflight import preflight_report

    report = preflight_report(database="failed", worker="ok", storage="ok")
    assert report["ready"] is False
