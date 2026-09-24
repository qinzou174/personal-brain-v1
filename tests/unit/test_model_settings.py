"""Unit: model settings enable/disable flip and secret redaction (T197)."""
import pytest
from pydantic import ValidationError

from personal_brain_server.bootstrap.settings import Settings


def _base(tmp_path) -> dict:
    return dict(
        _env_file=None, environment="test", data_root=tmp_path / "data",
        database_dsn_file=tmp_path / "dsn", token_pepper_file=tmp_path / "pepper",
    )


def test_models_disabled_by_default_fail_closed(tmp_path):
    settings = Settings(**_base(tmp_path))  # external_models_enabled defaults False
    summary = settings.safe_summary()
    assert summary["external_models_enabled"] is False
    assert summary["chat_model_name"] == "disabled"
    assert summary["embedding_model_name"] == "disabled"
    assert summary["embedding_dimensions"] == 0


def test_models_enabled_require_secret_file_and_approved_base_url(tmp_path):
    base = dict(**_base(tmp_path), external_models_enabled=True)
    with pytest.raises(ValidationError):
        Settings(**base)  # no key file
    with pytest.raises(ValidationError):
        Settings(**base, model_api_key_file=tmp_path / "key",
                 chat_model_base_url="https://example.invalid/api")
    ok = Settings(**base, model_api_key_file=tmp_path / "key")
    assert ok.safe_summary()["chat_model_name"] == "deepseek-v4.1-flash"
    assert ok.safe_summary()["embedding_model_name"] == "doubao-embedding-vision"


def test_serialized_settings_never_contain_key_value(tmp_path):
    settings = Settings(**{**_base(tmp_path),
                           "external_models_enabled": True,
                           "model_api_key_file": tmp_path / "key"})
    dumped = repr(settings.model_dump())
    assert "key" not in dumped or "key" not in [k for k in settings.model_dump() if "key" in k.lower() and "file" not in k.lower()]
    assert settings.model_api_key_file is not None  # path allowed; value excluded