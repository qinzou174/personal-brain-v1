"""Secret-safe logging with correlation IDs and bounded rotation.

FR-070/FR-072/FR-093: credentials and secret-like values never appear in routine
logs; every request carries a correlation ID that survives into the log record;
log files rotate under a bounded size/count policy so growth is controlled.
"""

from __future__ import annotations

import logging
from typing import Any

# Known-value field names that may carry private content and must never be emitted.
_PRIVATE_FIELDS = frozenset({
    "body", "request_body", "content", "credential", "token", "secret",
    "source_body", "password", "api_key", "authorization",
})

_DEFAULT_ROTATION = {"max_bytes": 10 * 1024 * 1024, "backup_count": 5, "encoding": "utf-8"}


class RedactingFilter(logging.Filter):
    """Drop private values carried on record extras without failing the call."""

    def filter(self, record: logging.LogRecord) -> bool:
        for field in _PRIVATE_FIELDS:
            if field in record.__dict__:
                record.__dict__[field] = "[REDACTED]"
        if hasattr(record, "extra"):
            extra = record.extra
            if isinstance(extra, dict):
                for key, value in list(extra.items()):
                    if key in _PRIVATE_FIELDS:
                        extra[key] = "[REDACTED]"
        return True


class CorrelationFormatter(logging.Formatter):
    """Include an optional correlation ID in every formatted line."""

    def format(self, record: logging.LogRecord) -> str:
        correlation_id = getattr(record, "correlation_id", None)
        record.correlation_id = correlation_id if correlation_id else "-"
        return super().format(record)


def rotation_settings(**overrides: Any) -> dict[str, Any]:
    """Return bounded rotation settings; callers may override size/count only within limits."""
    settings = dict(_DEFAULT_ROTATION)
    if "max_bytes" in overrides:
        value = int(overrides["max_bytes"])
        if value < 1_000_000 or value > 1_073_741_824:
            raise ValueError("log max_bytes out of bounds")
        settings["max_bytes"] = value
    if "backup_count" in overrides:
        value = int(overrides["backup_count"])
        if value < 1 or value > 90:
            raise ValueError("log backup_count out of bounds")
        settings["backup_count"] = value
    return settings
