"""Portable export/import contract (T149)."""


def test_manifest_excludes_credentials_and_maps_sources_blobs():
    from personal_brain_domain.operations.export import build_portable_manifest

    manifest = build_portable_manifest(schema_version="v1", source_ids=("s1", "s2"), blob_manifest={"b1": "h1"})
    assert manifest.excludes_credentials is True
    assert manifest.source_ids == ("s1", "s2")
    assert manifest.blob_manifest == {"b1": "h1"}
