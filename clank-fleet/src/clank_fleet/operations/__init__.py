"""Fleet control adapter boundaries (Stage 0).

All concrete implementations are absent. Callers receive OperationResult
with state NOT_IMPLEMENTED.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from clank_runtime.contracts.operations import OperationResult, OperationType


@runtime_checkable
class FleetControlAdapter(Protocol):
    """Protocol for fleet-level and per-clank control operations."""

    def status(self, clank_id: str | None = None) -> OperationResult: ...
    def run_now(self, clank_id: str) -> OperationResult: ...
    def pause(self, clank_id: str) -> OperationResult: ...
    def resume(self, clank_id: str) -> OperationResult: ...
    def restart(self, clank_id: str) -> OperationResult: ...
    def deploy(self, clank_id: str, **kwargs: object) -> OperationResult: ...
    def rollback(self, clank_id: str, **kwargs: object) -> OperationResult: ...
    def backup(self, clank_id: str | None = None) -> OperationResult: ...
    def restore(self, clank_id: str | None = None, **kwargs: object) -> OperationResult: ...
    def diagnostics(self, clank_id: str | None = None) -> OperationResult: ...
    def retrieve_logs(self, clank_id: str, **kwargs: object) -> OperationResult: ...


class AbstractFleetControlAdapter:
    """Abstract base that returns NOT_IMPLEMENTED for Stage 0."""

    def _not_implemented(self, op: OperationType, clank_id: str | None = None) -> OperationResult:
        return OperationResult(
            operation_id=f"stage0-{op.value}",
            operation_type=op,
            message="Not implemented in Stage 0",
            error_code="STAGE0_NOT_IMPLEMENTED",
            details={"clank_id": clank_id} if clank_id else {},
        )

    def status(self, clank_id: str | None = None) -> OperationResult:
        return self._not_implemented(OperationType.STATUS, clank_id)

    def run_now(self, clank_id: str) -> OperationResult:
        return self._not_implemented(OperationType.RUN_NOW, clank_id)

    def pause(self, clank_id: str) -> OperationResult:
        return self._not_implemented(OperationType.PAUSE, clank_id)

    def resume(self, clank_id: str) -> OperationResult:
        return self._not_implemented(OperationType.RESUME, clank_id)

    def restart(self, clank_id: str) -> OperationResult:
        return self._not_implemented(OperationType.RESTART, clank_id)

    def deploy(self, clank_id: str, **kwargs: object) -> OperationResult:
        return self._not_implemented(OperationType.DEPLOY, clank_id)

    def rollback(self, clank_id: str, **kwargs: object) -> OperationResult:
        return self._not_implemented(OperationType.ROLLBACK, clank_id)

    def backup(self, clank_id: str | None = None) -> OperationResult:
        return self._not_implemented(OperationType.BACKUP, clank_id)

    def restore(self, clank_id: str | None = None, **kwargs: object) -> OperationResult:
        return self._not_implemented(OperationType.RESTORE, clank_id)

    def diagnostics(self, clank_id: str | None = None) -> OperationResult:
        return self._not_implemented(OperationType.DIAGNOSTICS, clank_id)

    def retrieve_logs(self, clank_id: str, **kwargs: object) -> OperationResult:
        return self._not_implemented(OperationType.LOG_RETRIEVAL, clank_id)
