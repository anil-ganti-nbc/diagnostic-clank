"""Health provider protocol.

STAGE 0.5 BOUNDARY — interface only. No real checks.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from clank_runtime.contracts.health import HealthPayload


@runtime_checkable
class HealthProvider(Protocol):
    """Produces a HealthPayload for the current process."""

    def get_health(self) -> HealthPayload:
        """Return current health information."""
        ...
