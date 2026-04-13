"""Simple event loop for browser actions."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Event
from typing import Any, Callable, Deque

from utils.logger import get_logger


@dataclass
class LoopEvent:
    """Queued event callback payload."""

    callback: Callable[..., Any]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]


class EventLoop:
    """Cooperative event loop for navigation and repaint tasks."""

    def __init__(self) -> None:
        """Initialize event queue and logger."""

        self._events: Deque[LoopEvent] = deque()
        self._running = Event()
        self.logger = get_logger("engine.event_loop")

    def post_event(self, callback: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Add an event callback to the queue."""

        self._events.append(LoopEvent(callback=callback, args=args, kwargs=kwargs))

    def tick(self) -> None:
        """Process all currently queued events."""

        while self._events:
            event = self._events.popleft()
            event.callback(*event.args, **event.kwargs)

    def start(self) -> None:
        """Mark loop as running."""

        self._running.set()
        self.logger.info("Event loop started")

    def stop(self) -> None:
        """Stop loop and clear pending events."""

        self._running.clear()
        self._events.clear()
        self.logger.info("Event loop stopped")
