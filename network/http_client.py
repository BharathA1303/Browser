"""Raw HTTP/HTTPS client based on sockets."""

from __future__ import annotations

from dataclasses import dataclass
import socket
from typing import Dict, Optional

from network.ssl_handler import SSLHandler
from network.url_parser import ParsedURL, URLParseError, URLParser
from utils.config import CONFIG
from utils.logger import get_logger


class HTTPClientError(RuntimeError):
    """Raised when low-level HTTP interactions fail."""


@dataclass
class HTTPResponse:
    """Represents a parsed HTTP response."""

    status_code: int
    reason: str
    headers: Dict[str, str]
    body: bytes
    url: ParsedURL

    @property
    def text(self) -> str:
        """Decode response body text using UTF-8 fallback."""

        return self.body.decode("utf-8", errors="replace")


class HTTPClient:
    """Simple HTTP client with redirect and POST support."""

    def __init__(self, timeout: int = CONFIG.network_timeout_seconds) -> None:
        """Create a client with default timeout and shared URL parser."""

        self.timeout = timeout
        self.url_parser = URLParser()
        self.ssl_handler = SSLHandler()
        self.logger = get_logger("network.http_client")

    def fetch(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        body: bytes | None = None,
        redirect_count: int = 0,
    ) -> HTTPResponse:
        """Fetch an HTTP resource using GET or POST with redirects."""

        try:
            parsed_url = self.url_parser.parse(url)
        except URLParseError as error:
            raise HTTPClientError(str(error)) from error

        if redirect_count > CONFIG.max_redirects:
            raise HTTPClientError("Too many redirects")

        method = method.upper()
        if method not in {"GET", "POST"}:
            raise HTTPClientError(f"Unsupported method: {method}")

        merged_headers: Dict[str, str] = {
            "Host": parsed_url.host,
            "User-Agent": CONFIG.user_agent,
            "Connection": "close",
            "Accept": "*/*",
        }
        if headers:
            merged_headers.update(headers)

        if body:
            merged_headers["Content-Length"] = str(len(body))

        request_line = f"{method} {parsed_url.path or '/'}"
        if parsed_url.query:
            request_line += f"?{parsed_url.query}"
        request_line += " HTTP/1.1\r\n"

        header_block = "".join(f"{key}: {value}\r\n" for key, value in merged_headers.items())
        request_bytes = (request_line + header_block + "\r\n").encode("utf-8")
        if body:
            request_bytes += body

        self.logger.info("Request %s %s", method, url)

        try:
            response_bytes = self._send_and_receive(parsed_url, request_bytes)
        except OSError as error:
            raise HTTPClientError(f"Network error: {error}") from error

        response = self._parse_response(response_bytes, parsed_url)

        if response.status_code in {301, 302, 303, 307, 308} and "location" in {
            key.lower() for key in response.headers.keys()
        }:
            location = self._header_lookup(response.headers, "Location")
            if not location:
                return response
            target = self._resolve_redirect(parsed_url, location)
            next_method = "GET" if response.status_code == 303 else method
            return self.fetch(
                target,
                method=next_method,
                headers=headers,
                body=body if next_method == "POST" else None,
                redirect_count=redirect_count + 1,
            )

        return response

    def _send_and_receive(self, parsed_url: ParsedURL, payload: bytes) -> bytes:
        """Open socket, send payload and receive complete response."""

        with socket.create_connection((parsed_url.host, parsed_url.port), timeout=self.timeout) as sock:
            sock.settimeout(self.timeout)
            connection: socket.socket
            if parsed_url.scheme == "https":
                connection = self.ssl_handler.wrap_socket(sock, server_hostname=parsed_url.host)
            else:
                connection = sock

            with connection:
                connection.sendall(payload)
                chunks: list[bytes] = []
                total = 0
                while True:
                    chunk = connection.recv(4096)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > CONFIG.max_response_size_bytes:
                        raise HTTPClientError("Response exceeded maximum configured size")
                return b"".join(chunks)

    def _parse_response(self, response_bytes: bytes, parsed_url: ParsedURL) -> HTTPResponse:
        """Parse status line, headers and body from raw HTTP response."""

        if b"\r\n\r\n" not in response_bytes:
            raise HTTPClientError("Invalid HTTP response")

        header_bytes, body = response_bytes.split(b"\r\n\r\n", 1)
        lines = header_bytes.decode("iso-8859-1", errors="replace").split("\r\n")
        status_line = lines[0]
        parts = status_line.split(" ", 2)
        if len(parts) < 2 or not parts[1].isdigit():
            raise HTTPClientError("Invalid HTTP status line")

        status_code = int(parts[1])
        reason = parts[2] if len(parts) > 2 else ""

        headers: Dict[str, str] = {}
        for line in lines[1:]:
            if not line or ":" not in line:
                continue
            key, value = line.split(":", 1)
            headers[key.strip()] = value.strip()

        if self._header_lookup(headers, "Transfer-Encoding").lower() == "chunked":
            body = self._decode_chunked(body)

        content_length = self._header_lookup(headers, "Content-Length")
        if content_length.isdigit():
            body = body[: int(content_length)]

        self.logger.info("Response %s %s bytes", status_code, len(body))
        return HTTPResponse(
            status_code=status_code,
            reason=reason,
            headers=headers,
            body=body,
            url=parsed_url,
        )

    @staticmethod
    def _header_lookup(headers: Dict[str, str], name: str) -> str:
        """Lookup header value using case-insensitive name."""

        for key, value in headers.items():
            if key.lower() == name.lower():
                return value
        return ""

    def _resolve_redirect(self, base: ParsedURL, location: str) -> str:
        """Resolve absolute and relative redirect targets."""

        location = location.strip()
        if "://" in location:
            return location
        if location.startswith("/"):
            return f"{base.scheme}://{base.host}:{base.port}{location}"

        base_path = base.path.rsplit("/", 1)[0] if "/" in base.path else ""
        return f"{base.scheme}://{base.host}:{base.port}{base_path}/{location}"

    def _decode_chunked(self, body: bytes) -> bytes:
        """Decode chunked transfer body."""

        output = bytearray()
        cursor = 0
        while cursor < len(body):
            line_end = body.find(b"\r\n", cursor)
            if line_end == -1:
                break
            size_hex = body[cursor:line_end].split(b";", 1)[0]
            try:
                size = int(size_hex.decode("ascii"), 16)
            except ValueError as error:
                raise HTTPClientError("Malformed chunk length") from error
            cursor = line_end + 2
            if size == 0:
                break
            output.extend(body[cursor : cursor + size])
            cursor += size + 2
        return bytes(output)
