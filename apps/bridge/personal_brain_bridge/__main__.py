"""Bridge entrypoint: ``python -m personal_brain_bridge`` starts the stdio MCP bridge.

FR-055/FR-098: stdout carries only JSON-RPC protocol lines; the bridge observes
only the approved workspace root and never echoes credentials.
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

from personal_brain_bridge.stdio import run_stdio_stream
from personal_brain_bridge.remote_proxy import RemoteMCPProxy, read_credential


def main() -> int:
    client_id = os.environ.get("BRAIN_BRIDGE_CLIENT_ID", "").strip()
    if not client_id:
        print("personal-brain-bridge: BRAIN_BRIDGE_CLIENT_ID is required", file=sys.stderr)
        return 2
    remote_url = os.environ.get("BRAIN_REMOTE_MCP_URL", "").strip()
    credential_file = os.environ.get("BRAIN_CREDENTIAL_FILE", "").strip()
    if not remote_url or not credential_file:
        print("personal-brain-bridge: remote URL and credential file are required", file=sys.stderr)
        return 2
    # JSON-RPC over stdio is UTF-8. Windows pipes default to a locale codec
    # (e.g. gbk + surrogateescape), which turns a UTF-8 client's bytes into
    # lone surrogates that later crash request encoding — pin the codecs.
    for stream in (sys.stdin, sys.stdout):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass
    try:
        proxy = RemoteMCPProxy(url=remote_url, credential=read_credential(credential_file))
        run_stdio_stream(sys.stdin, sys.stdout, authorized_client_id=client_id, remote_proxy=proxy)
        proxy.close()
        return 0
    except (OSError, ValueError) as error:
        # class name + innermost code frame only — never the message, which
        # could carry a credential path or response payload
        frame = traceback.extract_tb(sys.exc_info()[2])[-1]
        print(f"personal-brain-bridge: secure configuration is invalid "
              f"({type(error).__name__} at {Path(frame.filename).name}:{frame.lineno})",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
