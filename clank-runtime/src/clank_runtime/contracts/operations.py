"""Operation result contract.

Stage 0.5 draft. Models only; no operation execution.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from clank_runtime.version import OPERATION_CONTRACT_VERSION


class OperationType(StrEnum):
    """Supported operation types (control plane)."""

    STATUS = "status"
    RUN_NOW = "run_now"
    PAUSE = "pause"
    RESUME = "resume"
    RESTART = "restart"
    DEPLOY = "deploy"
    ROLLBACK = "rollback"
    BACKUP = "backup"
    RESTORE = "restore"
    DIAGNOSTICS = "diagnostics"
    LOG_RETRIEVAL = "log_retrieval"


class OperationState(StrEnum):
    """Lifecycle state of a requested operation."""

    REQUESTED = "requested"
    ACCEPTED = "accepted"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    NOT_IMPLEMENTED = "not_implemented"


class OperationResult(BaseModel):
    """Result of a control-plane operation request.

    In Stage 0 / 0.5 every concrete adapter returns NOT_IMPLEMENTED.
    """

    model_config = ConfigDict(extra="forbid")

    contract_version: str = Field(default=OPERATION_CONTRACT_VERSION, min_length=1)
    operation_id: str = Field(..., min_length=1)
    operation_type: OperationType
    state: OperationState = OperationState.NOT_IMPLEMENTED
    requested_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    message: str = "Not implemented in Stage 0"
    error_code: str | None = "STAGE0_NOT_IMPLEMENTED"
    correlation_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
