"""Clank Ledger contract — human HIT/MISS records independent of ClankOps.

Join keys to telemetry: lead_id preferred; else (clank_id, date, source_url).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from clank_runtime.contracts.enums import LedgerOutcome
from clank_runtime.version import LEDGER_CONTRACT_VERSION


class LedgerEntry(BaseModel):
    """One human Ledger row."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default=LEDGER_CONTRACT_VERSION, min_length=1)
    ledger_id: str = Field(default_factory=lambda: str(uuid4()))
    recorded_at: datetime
    entry_date: date
    clank_id: str = Field(..., min_length=1, pattern=r"^[a-z][a-z0-9-]*$")
    lead_id: str | None = Field(
        default=None,
        description="Join key to telemetry lead_id when known.",
    )
    source_url: str | None = None
    outcome: LedgerOutcome = LedgerOutcome.PENDING
    importance: str | None = None
    category: str | None = None
    note: str | None = None
    qualitative_performance: str | None = None
    # Offline queue support
    originated_offline: bool = False
    synced_at: datetime | None = None
    extensions: dict[str, Any] = Field(default_factory=dict)


def ledger_join_keys(entry: LedgerEntry) -> dict[str, str | None]:
    """Keys useful for joining to telemetry without requiring ClankOps."""
    return {
        "ledger_id": entry.ledger_id,
        "clank_id": entry.clank_id,
        "lead_id": entry.lead_id,
        "source_url": entry.source_url,
        "entry_date": entry.entry_date.isoformat(),
    }
