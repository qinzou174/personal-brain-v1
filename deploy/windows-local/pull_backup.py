"""Pull the newest production backup bundle onto this machine (local-only).

Off-host copy: the server writes encrypted bundles next to the deployment, this
script fetches the newest one over SSH and verifies its sha256 locally, so the
"machine dies with the only copy on it" scenario stops being possible.
"""
from __future__ import annotations

import hashlib
import posixpath
import sys
from pathlib import Path

import paramiko

from _ssh import HOST, USER, open_client, password

REMOTE_DIR = "/home/kms/deploy/personal-brain/backups"
LOCAL_DIR = Path(r"E:\Personal-Brain-V1-local\backups")


def main() -> int:
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    transport = paramiko.Transport((HOST, 22))
    transport.connect(username=USER, password=password())
    sftp = paramiko.SFTPClient.from_transport(transport)
    try:
        bundles = [name for name in sftp.listdir(REMOTE_DIR) if name.endswith(".tar.age")]
        if not bundles:
            print("no bundles on the server yet")
            return 1
        newest = max(bundles, key=lambda name: sftp.stat(posixpath.join(REMOTE_DIR, name)).st_mtime)
        remote = posixpath.join(REMOTE_DIR, newest)
        target = LOCAL_DIR / newest
        size = sftp.stat(remote).st_size
        sftp.get(remote, str(target))
        with sftp.open(remote + ".sha256") as stream:
            expected = stream.read().decode().split()[0]
    finally:
        sftp.close()
        transport.close()

    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    ok = digest == expected
    print(f"pulled={target} bytes={size} sha256_match={ok}")
    if not ok:
        target.unlink(missing_ok=True)
        print("checksum mismatch: local copy removed")
        return 1
    existing = sorted(LOCAL_DIR.glob("personal-brain-prod-*.tar.age"))[:-5]
    for stale in existing:
        stale.unlink()
        stale.with_suffix(".tar.age.sha256").unlink(missing_ok=True)
    print(f"offsite_kept={len(list(LOCAL_DIR.glob('personal-brain-prod-*.tar.age')))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())