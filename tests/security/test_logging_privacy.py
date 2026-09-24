"""Secret-safe logging, correlation IDs and rotation settings (FR-070/072/093)."""

import logging

import pytest


def test_log_extra_redacts_secret_like_values():
    from personal_brain_server.bootstrap.logging import RedactingFilter

    record = logging.LogRecord(
        name="brain", level=logging.INFO, pathname=__file__, lineno=1,
        msg="%s connected", args=("client-a",), exc_info=None,
    )
    marker = "never-print-this-secret-token"
    record.__dict__["extra"] = {"body": marker, "credential": marker}
    RedactingFilter().filter(record)
    encoded = record.getMessage()
    assert marker not in encoded


def test_formatter_injects_correlation_id_when_present():
    from personal_brain_server.bootstrap.logging import CorrelationFormatter

    record = logging.LogRecord(
        name="brain", level=logging.INFO, pathname=__file__, lineno=1,
        msg="op done", args=(), exc_info=None,
    )
    record.correlation_id = "corr-9"
    formatted = CorrelationFormatter("%(correlation_id)s %(message)s").format(record)
    assert formatted == "corr-9 op done"


def test_rotation_settings_are_bounded_and_default():
    from personal_brain_server.bootstrap.logging import rotation_settings

    settings = rotation_settings()
    assert settings["max_bytes"] >= 1_000_000
    assert 1 <= settings["backup_count"] <= 90
    assert settings["encoding"] == "utf-8"
