"""US7 security boundaries: secret corpus, workspace escape, denial-before-search (T084)."""

import pytest


def test_secret_corpus_never_enters_ordinary_storage():
    from personal_brain_domain.intake.security_pipeline import check_before_persistence
    from personal_brain_domain.security.secret_filter import detect_secret

    corpus = [
        ("api_key=sk-live-abcdef", True),
        ("AKIA1234567890ABCDEF", True),
        ("-----BEGIN RSA PRIVATE KEY-----", True),
        ("bearer eyJhbGciOiJIUzI1NiJ9.abcdefghijklmnopqrstuvwxyz123456", True),
        ("我的私人日记内容", False),
        ("price=12.50 CNY", False),
    ]
    for content, expected_secret in corpus:
        detection = detect_secret(filename="f.txt", content_type="text/plain", content=content)
        assert detection.matched is expected_secret
        if expected_secret:
            with pytest.raises(Exception):
                check_before_persistence(filename="f.txt", content_type="text/plain", content=content)


def test_workspace_escape_rejected_before_read():
    from personal_brain_bridge.workspace_boundary import resolve_within_workspace

    root = "/home/kms/workspace"
    for attack in ("../secret.txt", "/etc/passwd", "sub/../../escape.txt"):
        with pytest.raises(Exception):
            resolve_within_workspace(root, attack)


def test_denial_before_search_no_candidate_access():
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_domain.retrieval.router import route_query

    calls = []
    route = route_query(
        intent="fuzzy idea search",
        scopes={"project"},
        client_id="project-only-client",
        grants=[],
        on_denied=lambda: calls.append("denied"),
    )
    assert calls == ["denied"]
    assert route is None
