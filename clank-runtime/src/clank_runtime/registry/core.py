"""Dynamic Clank registry — identities are data, not source enums."""
from __future__ import annotations
from datetime import UTC, datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

class ClankRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clank_id: str = Field(..., min_length=1, pattern=r"^[a-z][a-z0-9-]*$")
    display_name: str | None = None
    domain: str | None = None
    adapter_id: str | None = None
    status: str = "registered"
    capabilities: list[str] = Field(default_factory=list)
    diagnostic_profile: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    registered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

class ClankRegistry:
    def __init__(self) -> None:
        self._items: dict[str, ClankRegistration] = {}
    def register(self, reg: ClankRegistration) -> None:
        self._items[reg.clank_id] = reg
    def get(self, clank_id: str) -> ClankRegistration | None:
        return self._items.get(clank_id)
    def require(self, clank_id: str) -> ClankRegistration:
        if clank_id == "fleet-wide":
            return ClankRegistration(clank_id="fleet-wide", display_name="Fleet-wide", domain="ops")
        reg = self.get(clank_id)
        if reg is None:
            raise KeyError(f"unknown_clank: {clank_id} — register before use")
        return reg
    def list_ids(self) -> list[str]:
        return sorted(self._items)
    def list_all(self) -> list[ClankRegistration]:
        return [self._items[k] for k in sorted(self._items)]
    def ensure_seed_examples(self) -> None:
        """No-op. Seeds belong in tests only — not a closed fleet enum in source."""
        return

DEFAULT_REGISTRY = ClankRegistry()
