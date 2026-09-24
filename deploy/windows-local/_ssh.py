"""Shared SSH connection factory for local-only ops scripts (safe to commit).

Credentials are NEVER hardcoded here. Resolution order:
  1. BRAIN_SSH_PASSWORD environment variable
  2. deploy/windows-local/_local_creds.txt (gitignored, single line = password)
"""
from __future__ import annotations

import os
import pathlib

import paramiko

HOST = os.environ.get("BRAIN_SSH_HOST", "192.168.10.7")
USER = os.environ.get("BRAIN_SSH_USER", "kms")
CREDS_FILE = pathlib.Path(__file__).resolve().parent / "_local_creds.txt"


def password() -> str:
    pwd = os.environ.get("BRAIN_SSH_PASSWORD", "")
    if pwd:
        return pwd
    if CREDS_FILE.exists():
        return CREDS_FILE.read_text(encoding="utf-8").strip()
    raise SystemExit(
        "SSH password missing: set BRAIN_SSH_PASSWORD or create "
        f"{CREDS_FILE} (one line, gitignored)"
    )


def open_client(timeout: int = 10) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=password(), timeout=timeout)
    return client
