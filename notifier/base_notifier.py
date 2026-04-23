"""Abstract base class for notification backends."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseNotifier(ABC):
    """Minimal notifier interface: one method to send a message string."""

    @abstractmethod
    def send(self, message: str) -> bool:
        """Send a single message. Returns True on success."""
