"""Health payload contract.

Stage 0.5 draft. Placeholders only. No actual health checks are implemented.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from clank_runtime.contracts.enums import IngestionState, OperationalState
from clank_runtime.version import HEALTH_CONTRACT_VERSION


class CollectorSummary(BaseModel):
    """Placeholder summary of collector activity.

    Counts only. No collector execution occurs in Stage 0 / 0.5.
    """

    model_config = ConfigDict(extra="forbid")

    total_collectors: int = Field(default=0, ge=0)
    active_collectors: int = Field(default=0, ge=0)
    failed_collectors: int = Field(default=0, ge=0)
    details: dict[str, Any] = Field(default_factory=dict)


class HealthPayload(BaseModel):
    """Health information reported by a clank.

    All fields are optional placeholders. Implementations must not claim
    functionality that does not exist in Stage 0 / 0.5.
    """

    model_config = ConfigDict(extra="forbid")

    contract_version: str = Field(default=HEALTH_CONTRACT_VERSION, min_length=1)
    operational_state: OperationalState = OperationalState.UNKNOWN
    process_liveness: bool | None = None
    application_readiness: bool | None = None
    last_attempted_run: datetime | None = None
    last_successful_run: datetime | None = None
    next_scheduled_run: datetime | None = None
    collector_summary: CollectorSummary | None = None
    database_writable: bool | None = Field(
        default=None,
        description="Placeholder only. No database access in Stage 0 / 0.5.",
    )
    evidence_path_writable: bool | None = None
    backup_freshness: datetime | None = None
    ingestion_state: IngestionState = IngestionState.UNKNOWN
    version_info: dict[str, str] = Field(default_factory=dict)
    status_reasons: list[str] = Field(default_factory=list)
    observed_at: datetime | None = None
