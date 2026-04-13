"""Custom URL parser without urllib."""

from __future__ import annotations

from dataclasses import dataclass
import re


class URLParseError(ValueError):
    """Raised when a URL cannot be parsed safely."""


@dataclass(frozen=True)
class ParsedURL:
    """Represents decomposed URL parts."""

    scheme: str
    host: str
    port: int
    path: str
    query: str
    fragment: str

    @property
    def authority(self) -> str:
        """Return host:port pair."""

        return f"{self.host}:{self.port}"

    @property
    def full_path(self) -> str:
        """Return path with query and fragment."""

        value = self.path or "/"
        if self.query:
            value += f"?{self.query}"
        if self.fragment:
            value += f"#{self.fragment}"
        return value


class URLParser:
    """Parse URLs into structured parts."""

    _URL_RE = re.compile(
        r"^(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*)://(?P<rest>.+)$"
    )

    @staticmethod
    def _decode_percent_encoded(value: str) -> str:
        """Decode %XX escape sequences while preserving invalid sequences."""

        result: list[str] = []
        index = 0
        while index < len(value):
            if value[index] == "%" and index + 2 < len(value):
                pair = value[index + 1 : index + 3]
                if re.fullmatch(r"[0-9a-fA-F]{2}", pair):
                    result.append(chr(int(pair, 16)))
                    index += 3
                    continue
            result.append(value[index])
            index += 1
        return "".join(result)

    def parse(self, url: str) -> ParsedURL:
        """Parse a URL into scheme, host, port, path, query and fragment."""

        if not url or not isinstance(url, str):
            raise URLParseError("URL must be a non-empty string")

        stripped = url.strip()
        match = self._URL_RE.match(stripped)
        if not match:
            raise URLParseError("URL must include a valid scheme such as http://")

        scheme = match.group("scheme").lower()
        if scheme not in {"http", "https"}:
            raise URLParseError(f"Unsupported URL scheme: {scheme}")

        rest = match.group("rest")
        fragment = ""
        if "#" in rest:
            rest, fragment = rest.split("#", 1)

        query = ""
        if "?" in rest:
            rest, query = rest.split("?", 1)

        if "/" in rest:
            authority, path = rest.split("/", 1)
            path = "/" + path
        else:
            authority = rest
            path = "/"

        authority = authority.strip()
        if not authority:
            raise URLParseError("URL host is missing")

        # IPv6 host format [::1]:443 support.
        host: str
        port_text: str | None = None
        if authority.startswith("["):
            if "]" not in authority:
                raise URLParseError("Invalid IPv6 URL host")
            host_end = authority.index("]")
            host = authority[1:host_end]
            tail = authority[host_end + 1 :]
            if tail.startswith(":"):
                port_text = tail[1:]
            elif tail:
                raise URLParseError("Invalid IPv6 authority section")
        else:
            if authority.count(":") > 1:
                raise URLParseError("Unexpected ':' in URL host")
            if ":" in authority:
                host, port_text = authority.rsplit(":", 1)
            else:
                host = authority

        host = host.strip().lower()
        if not host:
            raise URLParseError("URL host is empty")

        if port_text is None or port_text == "":
            port = 443 if scheme == "https" else 80
        else:
            if not port_text.isdigit():
                raise URLParseError("URL port must be numeric")
            port = int(port_text)
            if not 1 <= port <= 65535:
                raise URLParseError("URL port out of valid range")

        decoded_path = self._decode_percent_encoded(path)
        decoded_query = self._decode_percent_encoded(query)
        decoded_fragment = self._decode_percent_encoded(fragment)

        return ParsedURL(
            scheme=scheme,
            host=host,
            port=port,
            path=decoded_path or "/",
            query=decoded_query,
            fragment=decoded_fragment,
        )
