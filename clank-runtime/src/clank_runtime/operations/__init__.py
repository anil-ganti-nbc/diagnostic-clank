"""Operation adapter protocol and diagnostics.

STAGE 0.5 BOUNDARY — interfaces only.
All concrete adapters raise NotImplementedError or return NOT_IMPLEMENTED.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from clank_runtime.contracts.operations import OperationResult, OperationType


@runtime_checkable
class OperationAdapter(Protocol):
    """Adapter for control-plane operations against a clank or fleet component."""

    def execute(self, operation_type: OperationType, **kwargs: object) -> OperationResult:
        """Execute or reject an operation. Stage 0.5 must return NOT_IMPLEMENTED."""
        ...


@runtime_checkable
class DiagnosticsProvider(Protocol):
    """Provides diagnostic information."""

    def get_diagnostics(self) -> dict[str, object]:
        """Return a diagnostics snapshot."""
        ...
