"""Pre-persistence secret gate for project, document, archive, log and search sinks.

FR-045/FR-072/ER-05: the secret filter runs before any ordinary persistence
surface. A matched secret produces a value-free SECRET_REJECTED decision; it must
never reach a project, document, archive, log, or search index.
"""

from __future__ import annotations

from dataclasses import dataclass

from personal_brain_domain.common.errors import BrainError
from personal_brain_domain.security.secret_filter import detect_secret

_PERSISTENCE_SINKS = ("project", "document", "archive", "log", "search")


@dataclass(frozen=True)
class PersistenceDecision:
    allowed: bool
    sinks: tuple[str, ...]
    rules: tuple[str, ...] = ()


def check_before_persistence(
    *,
    filename: str,
    content_type: str | None = None,
    content: str | None = None,
) -> PersistenceDecision:
    """Gate every ordinary persistence sink behind the secret filter."""
    detection = detect_secret(filename=filename, content_type=content_type, content=content)
    if detection.matched:
        raise BrainError("SECRET_REJECTED")
    return PersistenceDecision(allowed=True, sinks=_PERSISTENCE_SINKS)
