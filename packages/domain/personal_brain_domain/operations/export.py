"""Owner-authorized portable export/import with schema/source/blob manifest.

Constitution I/FR-040/FR-076/FR-094: export/import excludes credentials and
caches; the manifest identifies schema version, sources and blobs.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortableManifest:
    schema_version: str
    source_ids: tuple[object, ...]
    blob_manifest: dict[str, str]
    excludes_credentials: bool = True


def build_portable_manifest(*, schema_version: str, source_ids: tuple[object, ...],
                            blob_manifest: dict[str, str]) -> PortableManifest:
    return PortableManifest(schema_version=schema_version, source_ids=source_ids,
                            blob_manifest=dict(blob_manifest))