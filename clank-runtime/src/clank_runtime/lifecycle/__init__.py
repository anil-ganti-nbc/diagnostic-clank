"""Lifecycle hooks.

STAGE 0.5 BOUNDARY — interface only.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class GracefulShutdownHook(Protocol):
    """Hook invoked during graceful shutdown."""

    def on_shutdown(self) -> None:
        """Perform cleanup. Must not block indefinitely."""
        ...
