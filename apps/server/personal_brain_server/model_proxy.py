"""Fixed-destination TCP relay for Ark from Docker hosts without bridge egress.

TLS remains end-to-end between the application and Ark.  The relay cannot read
HTTP headers, API keys or payloads and accepts connections only on docker0.
"""

from __future__ import annotations

import os
from pathlib import Path
import selectors
import socket
import socketserver


TARGET_HOST = "ark.cn-beijing.volces.com"
TARGET_PORT = 443


class _Relay(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        try:
            upstream = socket.create_connection((TARGET_HOST, TARGET_PORT), timeout=15)
        except OSError:
            return
        with upstream:
            self.request.setblocking(False)
            upstream.setblocking(False)
            selector = selectors.DefaultSelector()
            selector.register(self.request, selectors.EVENT_READ, upstream)
            selector.register(upstream, selectors.EVENT_READ, self.request)
            try:
                while True:
                    events = selector.select(timeout=60)
                    if not events:
                        return
                    for key, _ in events:
                        try:
                            data = key.fileobj.recv(65536)
                        except OSError:
                            return
                        if not data:
                            return
                        destination = key.data
                        try:
                            destination.sendall(data)
                        except OSError:
                            return
            finally:
                selector.close()


class _Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True


def main() -> int:
    socket_path = Path(os.environ.get("BRAIN_MODEL_PROXY_SOCKET", "/run/model-proxy/ark.sock"))
    if socket_path != Path("/run/model-proxy/ark.sock"):
        return 2
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    if socket_path.exists() or socket_path.is_socket():
        if not socket_path.is_socket():
            return 2
        socket_path.unlink()
    try:
        with _Server(str(socket_path), _Relay) as server:
            socket_path.chmod(0o660)
            server.serve_forever(poll_interval=0.5)
    finally:
        if socket_path.is_socket():
            socket_path.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
