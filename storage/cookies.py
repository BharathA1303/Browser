"""Cookie storage and expiration management."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional


@dataclass
class Cookie:
    """Represents one HTTP cookie."""

    name: str
    value: str
    domain: str
    path: str = "/"
    expires_at: Optional[datetime] = None

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        """Return True if cookie has expired."""

        if self.expires_at is None:
            return False
        now = now or datetime.utcnow()
        return now >= self.expires_at


class CookieManager:
    """Store and retrieve cookies by domain and path scope."""

    def __init__(self) -> None:
        """Initialize internal cookie storage."""

        self._store: Dict[str, List[Cookie]] = {}

    def set_cookie(
        self,
        name: str,
        value: str,
        domain: str,
        path: str = "/",
        max_age_seconds: Optional[int] = None,
    ) -> None:
        """Create or update a cookie record."""

        expires_at = None
        if max_age_seconds is not None:
            expires_at = datetime.utcnow() + timedelta(seconds=max_age_seconds)

        cookie = Cookie(name=name, value=value, domain=domain.lower(), path=path, expires_at=expires_at)
        cookies = self._store.setdefault(cookie.domain, [])

        for idx, existing in enumerate(cookies):
            if existing.name == name and existing.path == path:
                cookies[idx] = cookie
                return
        cookies.append(cookie)

    def get_cookies(self, domain: str, path: str = "/") -> Dict[str, str]:
        """Return non-expired cookie name/value pairs for request scope."""

        domain = domain.lower()
        now = datetime.utcnow()
        result: Dict[str, str] = {}

        for stored_domain, cookies in list(self._store.items()):
            if not (domain == stored_domain or domain.endswith(f".{stored_domain}")):
                continue

            valid_cookies: List[Cookie] = []
            for cookie in cookies:
                if cookie.is_expired(now):
                    continue
                if not path.startswith(cookie.path):
                    continue
                result[cookie.name] = cookie.value
                valid_cookies.append(cookie)
            self._store[stored_domain] = valid_cookies

        return result

    def clear_expired(self) -> None:
        """Purge all expired cookies."""

        now = datetime.utcnow()
        for domain, cookies in list(self._store.items()):
            self._store[domain] = [cookie for cookie in cookies if not cookie.is_expired(now)]
