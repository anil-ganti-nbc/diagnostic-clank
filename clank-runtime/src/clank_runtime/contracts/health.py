"""Health payload contract — Architecture v3.

Source-specific zero semantics remain Clank-owned. Fleet consumes declared
source health status. Evidence: Watch Clank product-catalogue ZERO_ITEMS
must not be reported as overall healthy.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from clank_runtime.contracts.enums import (
    FailureClass,
    OperationalState,
    SourceHealthStatus,
)
from clank_runtime.version import HEALTH_CONTRACT_VERSION


class SourceHealthEntry(BaseModel):
    """Per-source health row for Fleet."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(..., min_length=1)
    status: SourceHealthStatus = SourceHealthStatus.UNKNOWN
    last_success_at: datetime | None = None
    last_attempt_at: datetime | None = None
    observed_count: int | None = Field(default=None, ge=0)
    previous_observed_count: int | None = Field(default=None, ge=0)
    expected_range_min: int | None = Field(default=None, ge=0)
    expected_range_max: int | None = Field(default=None, ge=0)
    health_reason: str | None = None
    failure_class: FailureClass | None = None
    warnings: list[str] = Field(default_factory=list)
    is_experimental: bool = False
    extensions: dict[str, Any] = Field(default_factory=dict)


class CollectorSummary(BaseModel):
    """Aggregate collector activity counts."""

    model_config = ConfigDict(extra="forbid")

    total_collectors: int = Field(default=0, ge=0)
    active_collectors: int = Field(default=0, ge=0)
    failed_collectors: int = Field(default=0, ge=0)
    warning_collectors: int = Field(default=0, ge=0)
    details: dict[str, Any] = Field(default_factory=dict)


class HealthPayload(BaseModel):
    """Fleet-facing health envelope for one Clank."""

    model_config = ConfigDict(extra="forbid")

    contract_version: str = Field(default=HEALTH_CONTRACT_VERSION, min_length=1)
    clank_id: str = Field(..., min_length=1, pattern=r"^[a-z][a-z0-9-]*$")
    overall_status: OperationalState = OperationalState.UNKNOWN
    run_status: str | None = None
    sources: list[SourceHealthEntry] = Field(default_factory=list)
    last_success_at: datetime | None = None
    last_attempt_at: datetime | None = None
    freshness: str | None = Field(
        default=None,
        description="current | delayed | stale | unknown",
    )
    is_stale_cache: bool = Field(
        default=False,
        description="True when this payload is from desktop cache, not live HQ.",
    )
    collector_summary: CollectorSummary = Field(default_factory=CollectorSummary)
    warnings: list[str] = Field(default_factory=list)
    failure_class: FailureClass | None = None
    observed_at: datetime | None = None
    extensions: dict[str, Any] = Field(default_factory=dict)
