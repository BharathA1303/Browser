"""Global browser configuration values."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BrowserConfig:
    """Immutable configuration used across browser modules."""

    default_window_width: int = 1200
    default_window_height: int = 800
    default_font_family: str = "Arial"
    default_font_size: int = 14
    max_redirects: int = 5
    network_timeout_seconds: int = 10
    max_response_size_bytes: int = 10_000_000
    user_agent: str = "BrowserV1/0.1"
    log_level: str = "INFO"


CONFIG = BrowserConfig()
