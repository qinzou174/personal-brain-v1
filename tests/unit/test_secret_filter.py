"""Secret-like filename/type/content detection and value-free results (T032, FR-072)."""

import pytest


def test_content_secret_like_values_are_detected_value_free():
    from personal_brain_domain.security.secret_filter import detect_secret

    result = detect_secret(
        filename="credentials.txt",
        content_type="text/plain",
        content="api_key=sk-live-abc123",
    )
    assert result.matched
    assert "sk-live-abc123" not in repr(result)
    assert "keychain" in result.rules
    assert "api_key_literal" in result.rules


def test_private_but_ordinary_content_is_not_rejected():
    from personal_brain_domain.security.secret_filter import detect_secret

    result = detect_secret(filename="note.md", content_type="text/markdown", content="My favorite color is blue.")
    assert not result.matched
    assert result.rule_list() == []


def test_filename_secret_keywords_alone_can_match():
    from personal_brain_domain.security.secret_filter import detect_secret

    assert detect_secret(filename="id_rsa", content_type="application/octet-stream", content="plain").matched
    assert detect_secret(filename=".env", content_type="text/plain", content="x=1").matched


@pytest.mark.parametrize("content", [
    "wifi_password=SimTest2026!x",
    "db_password=hunter2secret",
    "app_secret=abcdef1234567890",
    "secret_key=abcdefghijklmnop",
])
def test_prefixed_credential_names_are_detected(content):
    """B-04 (SIMTEST S-76): underscore/dash-prefixed names (wifi_password,
    db_password, app_secret, secret_key) have no word boundary before the
    keyword and escaped the literal rules — they must be detected too."""
    from personal_brain_domain.security.secret_filter import detect_secret

    result = detect_secret(filename="f.txt", content_type="text/plain", content=content)
    assert result.matched, f"{content!r} escaped the secret filter"


def test_plain_prose_mentioning_the_word_is_not_flagged():
    """A prose sentence with '='-free keyword mention stays clean."""
    from personal_brain_domain.security.secret_filter import detect_secret

    result = detect_secret(filename="note.md", content_type="text/markdown",
                           content="请把 password 改成强一点的再发我。")
    assert not result.matched
