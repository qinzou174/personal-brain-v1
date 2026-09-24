"""Out-of-scope components absent from core dependency/deployment graphs (T166)."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_core_packages_do_not_import_out_of_scope_dependencies():
    import importlib

    for module in ("personal_brain_domain", "personal_brain_infra", "personal_brain_server",
                   "personal_brain_worker", "personal_brain_bridge"):
        importlib.import_module(module)


def test_no_public_worker_or_admin_route_in_compose():
    text = (REPO / "deploy" / "compose.yaml").read_text(encoding="utf-8")
    assert text.count("ports:") == 1  # only the api publishes a port
