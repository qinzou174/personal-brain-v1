"""Proposed deployment boundary checks (T042, FR-075/093/100)."""

from pathlib import Path
import re

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_compose_has_no_published_db_or_worker_port():
    text = (REPO_ROOT / "deploy" / "compose.yaml").read_text(encoding="utf-8")
    # Only the api service may publish the approved LAN port; db/worker stay internal.
    assert "192.168.10.7:18081:18081" in text
    assert text.count("ports:") == 1
    assert "BRAIN_BIND_HOST: 0.0.0.0" in text
    assert "BRAIN_PUBLISHED_HOST: 192.168.10.7" in text
    assert 'BRAIN_CONTAINERIZED: "true"' in text


def test_compose_mounts_every_referenced_secret_file():
    text = (REPO_ROOT / "deploy" / "compose.yaml").read_text(encoding="utf-8")
    assert "BRAIN_DB_PASSWORD_FILE" in text
    assert "secrets: [db_password]" in text
    assert text.count("secrets: [db_dsn, token_pepper, model_api_key]") == 2
    assert "BRAIN_MODEL_API_KEY_FILE" in text
    assert "file: ${BRAIN_MODEL_API_KEY_FILE:?set BRAIN_MODEL_API_KEY_FILE}" in text
    assert "file: ${BRAIN_DB_PASSWORD_FILE:?set BRAIN_DB_PASSWORD_FILE}" in text
    assert "file: ${BRAIN_DB_DSN_FILE:?set BRAIN_DB_DSN_FILE}" in text
    assert "file: ${BRAIN_TOKEN_PEPPER_FILE:?set BRAIN_TOKEN_PEPPER_FILE}" in text


def test_compose_runs_migrations_before_api_and_worker():
    text = (REPO_ROOT / "deploy" / "compose.yaml").read_text(encoding="utf-8")
    assert 'command: ["alembic", "upgrade", "head"]' in text
    assert text.count("condition: service_completed_successfully") == 2
    assert text.count("image: personal-brain-v1-runtime:local") == 4
    assert "network: host" in text
    assert "network_mode: host" in text
    assert "BRAIN_MODEL_PROXY_SOCKET: /run/model-proxy/ark.sock" in text
    assert text.count("networks: [internal]") == 4
    assert "model-egress" not in text


def test_compose_never_embeds_secrets():
    for path in (REPO_ROOT / "deploy" / "compose.yaml",):
        text = path.read_text(encoding="utf-8")
        assert "POSTGRES_PASSWORD=" not in text
        assert not re.search(r"(?im)^\s*(?:password|secret|token)\s*:\s*\S+", text)
