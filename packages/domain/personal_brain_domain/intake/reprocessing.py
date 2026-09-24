"""Reprocessing activation/supersession without canonical mutation.

FR-007/FR-086/ER-01/ER-02: reprocessing an immutable canonical input creates a
distinguishable new derivation and never rewrites the original; the new active
derivation supersedes the prior one while prior interpretation history remains.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from personal_brain_domain.intake.lineage import DerivationIdentity


@dataclass(frozen=True)
class Reprocessed:
    raw_input_id: str
    raw_text: str
    derivation_id: str
    generator_version: str
    previous_derivation_id: str | None = None
    state: str = "active"


def reprocess(*, raw_input_id: str, text: str, generator_version: str,
              previous_derivation_id: str | None = None) -> Reprocessed:
    """Produce a new derivation generation from the immutable raw input.

    The canonical raw text is returned as-is (never rewritten); every call yields
    a fresh derivation identity, and the caller may supersede the prior one.
    """
    identity = DerivationIdentity(generator_kind="reprocessor", generator_version=generator_version)
    return Reprocessed(
        raw_input_id=raw_input_id,
        raw_text=text,
        derivation_id=str(identity.derivation_id),
        generator_version=generator_version,
        previous_derivation_id=previous_derivation_id,
        state="active",
    )
