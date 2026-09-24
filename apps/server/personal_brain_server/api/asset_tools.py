"""Streamed upload_asset application operation.

FR-031..FR-040/FR-099: upload_asset verifies bytes, dedupes by (sha256, size)
and returns an asset identity; the caller never chooses the storage path.
"""

from __future__ import annotations

from dataclasses import dataclass

from personal_brain_domain.assets.intake import AdmittedAsset, admit_asset
from personal_brain_domain.common.errors import BrainError


@dataclass(frozen=True)
class UploadResult:
    asset_id: str
    blob_id: str
    sha256: str
    deduplicated: bool


def upload_asset(*, content: bytes, original_name: str, source_id: object,
                 existing_blobs: dict[str, str]) -> UploadResult:
    """Deduplicate by content identity; return the existing blob when already present."""
    try:
        admitted = admit_asset(content=content, original_name=original_name, source_id=source_id)
    except ValueError:
        raise BrainError("PAYLOAD_TOO_LARGE") from None
    if admitted.sha256 in existing_blobs:
        return UploadResult(asset_id=admitted.asset_id, blob_id=existing_blobs[admitted.sha256],
                            sha256=admitted.sha256, deduplicated=True)
    return UploadResult(asset_id=admitted.asset_id, blob_id=admitted.blob_id,
                        sha256=admitted.sha256, deduplicated=False)