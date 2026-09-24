"""Provenance explanation queries (why does the Brain believe this?).

FR-030/FR-065: provenance answers expose supporting evidence, source class,
confidence basis, generator version, and applicable time/context — never raw
private bodies.
"""

from __future__ import annotations

from dataclasses import dataclass

from personal_brain_domain.memory.source_policy import source_class_label


@dataclass(frozen=True)
class ProvenanceExplanation:
    claim_id: str
    source_class: str
    evidence_ids: tuple[str, ...]
    generator_version: str
    time_context: str | None = None
    confidence_basis: str | None = None

    def to_mapping(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "source_class": self.source_class,
            "source_class_label": source_class_label(self.source_class),
            "evidence_ids": list(self.evidence_ids),
            "generator_version": self.generator_version,
            "time_context": self.time_context,
            "confidence_basis": self.confidence_basis,
        }


def explain_belief(*, claim_id: str, source_class: str, evidence_ids: tuple[str, ...],
                   generator_version: str, time_context: str | None = None,
                   confidence_basis: str | None = None) -> dict[str, object]:
    """Explain one belief with class, evidence, version and time/context."""
    return ProvenanceExplanation(
        claim_id=claim_id,
        source_class=source_class,
        evidence_ids=tuple(evidence_ids),
        generator_version=generator_version,
        time_context=time_context,
        confidence_basis=confidence_basis,
    ).to_mapping()
