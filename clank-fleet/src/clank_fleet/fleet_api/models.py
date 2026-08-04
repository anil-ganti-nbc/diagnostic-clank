"""API request/response models and error envelope (Stage 0.5).

All behavior endpoints return NotImplementedResponse with HTTP 501.
PingResponse must never claim fleet, storage, or ingestion health.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from clank_fleet import API_CONTRACT_VERSION, __version__


class ErrorEnvelope(BaseModel):
    """Standard error response shape for the Fleet API."""

    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None
    api_contract_version: str = API_CONTRACT_VERSION


class PingResponse(BaseModel):
    """Process-level shell check only.

    Does **not** claim: fleet health, clank liveness, storage, ingestion, backups.
    """

    model_config = ConfigDict(extra="forbid")

    status: str = "ok"
    message: str = "Fleet API shell is running (Stage 0)"
    api_contract_version: str = API_CONTRACT_VERSION
    application_version: str = __version__


class ClankMetadata(BaseModel):
    """Placeholder clank metadata model for future list/detail responses."""

    model_config = ConfigDict(extra="forbid")

    clank_id: str = Field(..., min_length=1)
    display_name: str | None = None
    version: str | None = None
    contract_version: str | None = None
    runtime_version: str | None = None
    release_channel: str | None = None
    operational_state: str | None = None


class NotImplementedResponse(BaseModel):
    """Body returned with HTTP 501 for all behavior-bearing endpoints."""

    model_config = ConfigDict(extra="forbid")

    error_code: str = "STAGE0_NOT_IMPLEMENTED"
    message: str = "Not implemented in Stage 0"
    api_contract_version: str = API_CONTRACT_VERSION
    details: dict[str, Any] = Field(default_factory=dict)
