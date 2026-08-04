"""Metadata provider protocol.

STAGE 0.5 BOUNDARY — interface only.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from clank_runtime.contracts.identity import RuntimeIdentity


@runtime_checkable
class MetadataProvider(Protocol):
    """Provides runtime identity and static metadata."""

    def get_identity(self) -> RuntimeIdentity:
        """Return the RuntimeIdentity for this instance."""
        ...
