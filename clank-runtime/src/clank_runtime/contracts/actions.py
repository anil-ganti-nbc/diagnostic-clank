"""Action safety classification for offline queue / reconnect.

Stale-sensitive and high-risk actions must NEVER auto-execute when HQ
returns after hours of offline time.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from clank_runtime.contracts.enums import ActionSafetyClass
from clank_runtime.contracts.operations import OperationType

# Default mapping of operation types to safety classes.
OPERATION_SAFETY: dict[OperationType, ActionSafetyClass] = {
    OperationType.STATUS: ActionSafetyClass.READ_ONLY,
    OperationType.DIAGNOSTICS: ActionSafetyClass.READ_ONLY,
    OperationType.LOG_RETRIEVAL: ActionSafetyClass.READ_ONLY,
    OperationType.RUN_NOW: ActionSafetyClass.STALE_SENSITIVE,
    OperationType.PAUSE: ActionSafetyClass.STALE_SENSITIVE,
    OperationType.RESUME: ActionSafetyClass.STALE_SENSITIVE,
    OperationType.RESTART: ActionSafetyClass.STALE_SENSITIVE,
    OperationType.DEPLOY: ActionSafetyClass.HIGH_RISK,
    OperationType.ROLLBACK: ActionSafetyClass.HIGH_RISK,
    OperationType.BACKUP: ActionSafetyClass.STALE_SENSITIVE,
    OperationType.RESTORE: ActionSafetyClass.HIGH_RISK,
}


class OfflineQueueItem(BaseModel):
    """An action or record queued while HQ was unreachable."""

    model_config = ConfigDict(extra="forbid")

    queue_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime
    safety_class: ActionSafetyClass
    action_type: str = Field(..., description="ledger_entry | note | operation | …")
    payload: dict[str, Any] = Field(default_factory=dict)
    clank_id: str | None = None
    requires_reconfirmation: bool = False
    auto_sync_eligible: bool = False
    synced_at: datetime | None = None
    discarded_reason: str | None = None


def classify_operation(op: OperationType) -> ActionSafetyClass:
    return OPERATION_SAFETY.get(op, ActionSafetyClass.HIGH_RISK)


def may_auto_sync(item: OfflineQueueItem) -> bool:
    """Only SAFE_OFFLINE items with auto_sync_eligible may sync without reconfirmation."""
    if item.synced_at is not None or item.discarded_reason is not None:
        return False
    if item.safety_class != ActionSafetyClass.SAFE_OFFLINE:
        return False
    if item.requires_reconfirmation:
        return False
    return item.auto_sync_eligible


def must_reconfirm(item: OfflineQueueItem) -> bool:
    return item.safety_class in (
        ActionSafetyClass.STALE_SENSITIVE,
        ActionSafetyClass.HIGH_RISK,
    ) or item.requires_reconfirmation
