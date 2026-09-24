"""US6 asset upload operation (T101)."""


def test_upload_asset_dedupes_by_content_identity():
    from personal_brain_server.api.asset_tools import upload_asset

    content = b"identical bytes"
    first = upload_asset(content=content, original_name="a.png", source_id="s1", existing_blobs={})
    second = upload_asset(content=content, original_name="b.png", source_id="s2",
                          existing_blobs={first.sha256: first.blob_id})
    assert second.deduplicated is True
    assert second.blob_id == first.blob_id
    assert second.asset_id != first.asset_id  # distinct source keeps distinct asset
