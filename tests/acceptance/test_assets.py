"""US6 Scenario D: asset identity, dedupe, integrity, archive safety (T091)."""

import hashlib

import pytest


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_duplicate_bytes_share_blob_but_keep_distinct_sources():
    from personal_brain_domain.assets.intake import admit_asset

    content = b"same bytes"
    first = admit_asset(content=content, original_name="a.txt", source_id="s1")
    second = admit_asset(content=content, original_name="b.txt", source_id="s2")
    assert first.blob_id == second.blob_id
    assert first.source_id != second.source_id
    assert first.sha256 == _sha256(content)


def test_integrity_detects_hash_mismatch():
    from personal_brain_domain.assets.integrity import verify_integrity

    assert verify_integrity(expected_sha256=_sha256(b"ok"), actual_bytes=b"ok") == "valid"
    assert verify_integrity(expected_sha256=_sha256(b"ok"), actual_bytes=b"tampered") == "hash_mismatch"


def test_archive_traversal_and_limits_rejected():
    from personal_brain_domain.assets.archive_processor import check_archive_listing

    with pytest.raises(Exception) as caught:
        check_archive_listing(entries=("../../etc/passwd",), max_entries=1000, max_name_chars=512)
    assert "traversal" in str(caught.value) or "boundary" in str(caught.value)
