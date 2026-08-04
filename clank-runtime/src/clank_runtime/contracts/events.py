"""Event envelope draft contract.

Stage 0.5 models only. No event writing, outbox, or deduplication.

See Architecture Amendment 4 (producer-owned spools) and Amendment 11
(multi-dimensional confidence). Those features are intentionally deferred.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from clank_runtime.version import EVENT_CONTRACT_VERSION


class EventEnvelope(BaseModel):
    """Immutable event envelope draft.

    Placeholders for identity, provenance, confidence, and payload.
    Do not write instances to disk in Stage 0 / 0.5.
    """

    model_config = ConfigDict(extra="forbid")

    contract_version: str = Field(default=EVENT_CONTRACT_VERSION, min_length=1)
    event_id: str = Field(..., min_length=1, description="Immutable unique event identifier.")
    producer: str = Field(
        ...,
        min_length=1,
        description="Producer identifier (clank_id or service).",
    )
    producer_version: str | None = None
    schema_name: str = Field(..., min_length=1, description="Logical schema name for the payload.")
    schema_version: str = Field(..., min_length=1, description="Version of the payload schema.")
    occurred_at: datetime | None = None
    observed_at: datetime | None = None
    source_references: list[str] = Field(default_factory=list)
    evidence_references: list[str] = Field(default_factory=list)
    domain_entity_references: list[str] = Field(default_factory=list)
    confidence_dimensions: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Multi-dimensional confidence scores. "
            "See clank_runtime.contracts.confidence for canonical keys. "
            "Never collapse to a single scalar."
        ),
    )
    payload: dict[str, Any] = Field(default_factory=dict)
    payload_hash: str | None = None
    correction_of: str | None = Field(
        default=None,
        description="Event ID this event corrects or supersedes, if any.",
    )
