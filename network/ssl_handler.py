"""TLS utilities for secure socket wrapping."""

from __future__ import annotations

import socket
import ssl


class SSLHandler:
    """Create secure SSL contexts and wrap sockets for HTTPS."""

    def __init__(self) -> None:
        """Initialize a strict SSL context."""

        self._context = ssl.create_default_context()
        self._context.check_hostname = True
        self._context.verify_mode = ssl.CERT_REQUIRED

    def wrap_socket(self, raw_socket: socket.socket, server_hostname: str) -> ssl.SSLSocket:
        """Wrap a socket with TLS using certificate validation."""

        return self._context.wrap_socket(raw_socket, server_hostname=server_hostname)
