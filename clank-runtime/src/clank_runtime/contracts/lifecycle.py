"""Source lifecycle and soak status contracts.

Promotion remains explicit (Great Audit SOURCE_PROMOTION_PROTOCOL).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from clank_runtime.contracts.enums import SourceLifecycleState


# Allowed transitions. Unknown transitions are rejected by helpers.
ALLOWED_SOURCE_TRANSITIONS: dict[SourceLifecycleState, frozenset[SourceLifecycleState]] = {
    SourceLifecycleState.DISCOVERED: frozenset(
        {SourceLifecycleState.RESEARCH, SourceLifecycleState.DISABLED}
    ),
    SourceLifecycleState.RESEARCH: frozenset(
        {
            SourceLifecycleState.EXPERIMENTAL,
            SourceLifecycleState.DISABLED,
            SourceLifecycleState.QUARANTINED,
        }
    ),
    SourceLifecycleState.EXPERIMENTAL: frozenset(
        {
            SourceLifecycleState.SOAK,
            SourceLifecycleState.DISABLED,
            SourceLifecycleState.QUARANTINED,
            SourceLifecycleState.RESEARCH,
        }
    ),
    SourceLifecycleState.SOAK: frozenset(
        {
            SourceLifecycleState.PRODUCTION,
            SourceLifecycleState.EXPERIMENTAL,
            SourceLifecycleState.DISABLED,
            SourceLifecycleState.QUARANTINED,
        }
    ),
    SourceLifecycleState.PRODUCTION: frozenset(
        {
            SourceLifecycleState.DISABLED,
            SourceLifecycleState.QUARANTINED,
            SourceLifecycleState.SOAK,  # demote for re-soak after major change
        }
    ),
    SourceLifecycleState.DISABLED: frozenset(
        {
            SourceLifecycleState.RESEARCH,
            SourceLifecycleState.EXPERIMENTAL,
            SourceLifecycleState.QUARANTINED,
        }
    ),
    SourceLifecycleState.QUARANTINED: frozenset(
        {
            SourceLifecycleState.DISABLED,
            SourceLifecycleState.RESEARCH,
            SourceLifecycleState.EXPERIMENTAL,
        }
    ),
}


def can_transition(current: SourceLifecycleState, target: SourceLifecycleState) -> bool:
    if current == target:
        return True
    return target in ALLOWED_SOURCE_TRANSITIONS.get(current, frozenset())


class SourceLifecycleRecord(BaseModel):
    """Declared lifecycle state for one source."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(..., min_length=1)
    clank_id: str = Field(..., min_length=1, pattern=r"^[a-z][a-z0-9-]*$")
    state: SourceLifecycleState
    updated_at: datetime | None = None
    evidence_summary: str | None = None
    operator: str | None = None
    extensions: dict[str, Any] = Field(default_factory=dict)


class SoakStatus(BaseModel):
    """Soak progress for an experimental/soak source."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    clank_id: str
    cycles_completed: int = Field(default=0, ge=0)
    cycles_required: int | None = Field(default=None, ge=0)
    failure_count: int = Field(default=0, ge=0)
    false_event_count: int = Field(default=0, ge=0)
    latest_run_healthy: bool | None = None
    promotion_gate_met: bool = False
    notes: str | None = None
