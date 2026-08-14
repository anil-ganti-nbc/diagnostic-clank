"""Failure taxonomy helpers.

Great Audit FAILURE_TAXONOMY — stable IDs for Fleet/ClankOps/Hermes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from clank_runtime.contracts.enums import FailureClass


class FailureReport(BaseModel):
    """A single classified failure observation."""

    model_config = ConfigDict(extra="forbid")

    failure_class: FailureClass = FailureClass.UNKNOWN
    failure_reason: str | None = None
    source_id: str | None = None
    run_id: str | None = None
    detected_at: datetime | None = None
    recoverable: bool | None = None
    extensions: dict[str, Any] = Field(default_factory=dict)
