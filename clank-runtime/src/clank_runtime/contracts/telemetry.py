"""Universal telemetry envelope (Great Audit CLANKOPS_TELEMETRY_DRAFT).

Adapters/exporters map Clank-internal schemas onto this envelope.
Internal DB rewrites are not required.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from clank_runtime.contracts.enums import (
    DeliveryStatus,
    FailureClass,
    RunKind,
    SourceHealthStatus,
)
from clank_runtime.version import TELEMETRY_CONTRACT_VERSION


class TelemetryEventRecord(BaseModel):
    """One alertable / lead-like event within a source run."""

    model_config = ConfigDict(extra="forbid")

    lead_id: str | None = Field(
        default=None,
        description="Stable event key for dedupe and Ledger join.",
    )
    source_url: str | None = None
    source_published_at: datetime | None = None
    detected_at: datetime | None = None
    classification: str | None = None
    classification_score: float | None = None
    classification_reason: str | None = None
    alerted: bool | None = None
    delivery_status: DeliveryStatus = DeliveryStatus.DELIVERY_UNKNOWN
    is_baseline: bool = False
    extensions: dict[str, Any] = Field(default_factory=dict)


class TelemetryEnvelope(BaseModel):
    """Per source-run telemetry export unit.

    schema_version tracks TELEMETRY_CONTRACT_VERSION.
    extensions is the only place for Clank-specific extra fields.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default=TELEMETRY_CONTRACT_VERSION, min_length=1)
    clank_id: str = Field(..., min_length=1, pattern=r"^[a-z][a-z0-9-]*$")
    run_id: str = Field(..., min_length=1)
    source_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    host_id: str | None = None
    trigger: str | None = Field(
        default=None,
        description="scheduled | manual | dashboard | soak | fallback | …",
    )
    run_kind: RunKind = RunKind.NORMAL_RUN

    source_status: SourceHealthStatus = SourceHealthStatus.UNKNOWN
    observed_count: int | None = Field(default=None, ge=0)
    accepted_count: int | None = Field(default=None, ge=0)
    rejected_count: int | None = Field(default=None, ge=0)
    previous_observed_count: int | None = Field(default=None, ge=0)
    catalog_fraction: float | None = None
    health_reason: str | None = None

    event_count: int | None = Field(default=None, ge=0)
    delivery_count: int | None = Field(default=None, ge=0)

    failure_class: FailureClass | None = None
    failure_reason: str | None = None

    events: list[TelemetryEventRecord] = Field(default_factory=list)
    extensions: dict[str, Any] = Field(default_factory=dict)
