from ipaddress import IPv4Address
from pathlib import Path

import pytest
from pydantic import ValidationError

from personal_brain_server.bootstrap.settings import Settings, read_secret_file


def config(tmp_path, **overrides):
    base = {
        "_env_file": None,
        "environment": "test",
        "data_root": tmp_path / "brain-data",
        "database_dsn_file": tmp_path / "brain-db",
        "token_pepper_file": tmp_path / "brain-pepper",
    }
    return Settings(**(base | overrides))


def test_settings_reject_all_interface_and_unapproved_production_bind(tmp_path):
    with pytest.raises(ValidationError):
        config(tmp_path, bind_host=IPv4Address("0.0.0.0"))
    with pytest.raises(ValidationError):
        config(tmp_path, environment="production", bind_host=IPv4Address("127.0.0.1"))
    assert config(tmp_path, environment="production", bind_host=IPv4Address("192.168.10.7")).bind_port == 18081


def test_container_listener_is_allowed_only_behind_approved_lan_publish(tmp_path):
    approved = config(
        tmp_path, environment="production", bind_host=IPv4Address("0.0.0.0"),
        published_host=IPv4Address("192.168.10.7"), containerized=True,
    )
    assert approved.containerized and approved.published_host == IPv4Address("192.168.10.7")
    with pytest.raises(ValidationError):
        config(
            tmp_path, environment="production", bind_host=IPv4Address("0.0.0.0"),
            published_host=IPv4Address("192.168.10.8"), containerized=True,
        )
    with pytest.raises(ValidationError):
        config(
            tmp_path, environment="production", bind_host=IPv4Address("192.168.10.7"),
            published_host=IPv4Address("192.168.10.7"), containerized=True,
        )


def test_secret_paths_are_excluded_from_diagnostics_and_repr(tmp_path):
    settings = config(tmp_path)
    diagnostic = repr(settings) + repr(settings.model_dump()) + repr(settings.safe_summary())
    assert "brain-db" not in diagnostic
    assert "brain-pepper" not in diagnostic


def test_secret_loader_redacts_value_and_rejects_empty(tmp_path):
    secret = tmp_path / "private"
    secret.write_text("never-print-this-value", encoding="utf-8")
    loaded = read_secret_file(secret)
    assert loaded.get_secret_value() == "never-print-this-value"
    assert "never-print-this-value" not in repr(loaded)
    secret.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        read_secret_file(secret)


def test_secret_loader_rejects_world_readable_regular_file_on_posix(tmp_path):
    if __import__("os").name != "posix":
        pytest.skip("POSIX permission contract")
    secret = tmp_path / "broad"
    secret.write_text("value", encoding="utf-8")
    secret.chmod(0o644)
    with pytest.raises(ValueError, match="permissions are too broad"):
        read_secret_file(secret)
