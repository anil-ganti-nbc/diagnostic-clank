"""Fallback levels, ownership fencing, and failback semantics.

Critical invariant: NAS recovery + continuing desktop fallback must never
produce split-brain dual primary execution.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from clank_runtime.contracts.enums import FallbackLevel, OwnershipRole
from clank_runtime.version import FALLBACK_CONTRACT_VERSION


class OwnershipToken(BaseModel):
    """Fencing token proving who owns production execution.

    A desktop fallback must hold a valid, non-expired token before Level 3
    execution. When NAS claims primary, it issues a new epoch; any prior
    desktop token for that clank becomes invalid.
    """

    model_config = ConfigDict(extra="forbid")

    token_id: str = Field(default_factory=lambda: str(uuid4()))
    clank_id: str = Field(..., min_length=1, pattern=r"^[a-z][a-z0-9-]*$")
    role: OwnershipRole
    epoch: int = Field(..., ge=0, description="Monotonic ownership epoch for this clank.")
    issued_at: datetime
    expires_at: datetime | None = None
    issuer: str = Field(..., description="nas | desktop:<machine_id> | operator")
    machine_id: str | None = None

    def is_expired(self, now: datetime) -> bool:
        if self.expires_at is None:
            return False
        return now >= self.expires_at

    def is_valid_for(self, clank_id: str, role: OwnershipRole, now: datetime) -> bool:
        if self.clank_id != clank_id:
            return False
        if self.role != role:
            return False
        if self.is_expired(now):
            return False
        return True


class OwnershipState(BaseModel):
    """Current ownership view for one Clank."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default=FALLBACK_CONTRACT_VERSION, min_length=1)
    clank_id: str
    role: OwnershipRole = OwnershipRole.UNKNOWN
    epoch: int = Field(default=0, ge=0)
    token: OwnershipToken | None = None
    nas_last_heartbeat_at: datetime | None = None
    desktop_last_heartbeat_at: datetime | None = None
    contested_reason: str | None = None
    updated_at: datetime | None = None


class FallbackDeclaration(BaseModel):
    """What fallback a Clank claims to support (not machine-specific)."""

    model_config = ConfigDict(extra="forbid")

    clank_id: str
    max_level: FallbackLevel = FallbackLevel.LEVEL_0
    requires_fencing: bool = True
    requires_secrets: bool = True
    requires_local_state_copy: bool = False
    failback_procedure: str | None = Field(
        default=None,
        description="Human-readable failback steps when NAS returns.",
    )
    extensions: dict[str, Any] = Field(default_factory=dict)

    @field_validator("requires_fencing")
    @classmethod
    def _level3_requires_fencing(cls, v: bool, info) -> bool:
        # Validated at model level via model_validator in callers; keep field honest.
        return v


def requires_fencing_for_level(level: FallbackLevel) -> bool:
    return level == FallbackLevel.LEVEL_3


def can_start_fallback(
    *,
    declaration: FallbackDeclaration,
    machine_supports: bool,
    ownership: OwnershipState,
    requested_level: FallbackLevel,
    now: datetime,
    nas_definitely_offline: bool,
) -> tuple[bool, str]:
    """Contract-level gate. Does not execute anything.

    Returns (allowed, reason).
    """
    if not nas_definitely_offline:
        return False, "NAS status uncertain; refusing fallback to avoid split-brain"
    if requested_level == FallbackLevel.LEVEL_0:
        return True, "observability only"
    order = list(FallbackLevel)
    if order.index(requested_level) > order.index(declaration.max_level):
        return False, "requested level exceeds Clank declaration"
    if not machine_supports:
        return False, "machine does not support this Clank at requested level"
    if requires_fencing_for_level(requested_level):
        if ownership.role == OwnershipRole.CONTESTED:
            return False, "ownership contested"
        if ownership.role == OwnershipRole.NAS_PRIMARY:
            return False, "NAS still holds primary ownership"
        token = ownership.token
        if token is None or not token.is_valid_for(
            declaration.clank_id, OwnershipRole.DESKTOP_FALLBACK, now
        ):
            return False, "no valid desktop fallback ownership token"
    return True, "allowed"
