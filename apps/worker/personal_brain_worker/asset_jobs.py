"""Versioned parse/transcribe/describe/embed handlers over verified bytes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from uuid import UUID


@dataclass(frozen=True)
class AssetJobOutcome:
    job_id: str
    state: str  # succeeded | dead_letter
    result_ref: str | None = None


def _handle(*, job_id: str, asset_id: UUID, generator_version: str, kind: str,
            generator_kind: str, service: object, transform: Callable[[bytes], bytes]) -> AssetJobOutcome:
    result = service.process(
        asset_id=asset_id, kind=kind, generator_kind=generator_kind,
        generator_version=generator_version, transform=transform,
    )
    return AssetJobOutcome(job_id=job_id, state="succeeded", result_ref=result["payload_ref"])


def handle_parse(*, job_id: str, asset_id: UUID, generator_version: str,
                 service: object, parser: Callable[[bytes], bytes]) -> AssetJobOutcome:
    return _handle(job_id=job_id, asset_id=asset_id, generator_version=generator_version,
                   kind="extracted_text", generator_kind="parser", service=service, transform=parser)


def handle_transcribe(*, job_id: str, asset_id: UUID, generator_version: str,
                      service: object, transcriber: Callable[[bytes], bytes]) -> AssetJobOutcome:
    return _handle(job_id=job_id, asset_id=asset_id, generator_version=generator_version,
                   kind="transcript", generator_kind="transcriber", service=service, transform=transcriber)


def handle_describe(*, job_id: str, asset_id: UUID, generator_version: str,
                    service: object, describer: Callable[[bytes], bytes]) -> AssetJobOutcome:
    return _handle(job_id=job_id, asset_id=asset_id, generator_version=generator_version,
                   kind="description", generator_kind="describer", service=service, transform=describer)


def handle_embed(*, job_id: str, asset_id: UUID, generator_version: str,
                 service: object, embedder: Callable[[bytes], bytes]) -> AssetJobOutcome:
    return _handle(job_id=job_id, asset_id=asset_id, generator_version=generator_version,
                   kind="embedding", generator_kind="embedder", service=service, transform=embedder)
