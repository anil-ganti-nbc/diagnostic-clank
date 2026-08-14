"""Local machine capability model for desktop fallback.

Different machines (Windows desktop, MacBook, Linux NAS client) must not
be assumed identical. Never pretend redundancy exists when the machine
lacks required state/secrets/runtime.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from clank_runtime.contracts.enums import FallbackLevel
from clank_runtime.version import MACHINE_CONTRACT_VERSION


class MachineCapabilities(BaseModel):
    """Declared capabilities of the local machine."""

    model_config = ConfigDict(extra="forbid")

    python_available: bool = False
    python_version: str | None = None
    docker_available: bool = False
    local_repo_checkout: bool = False
    secrets_available: bool = False
    local_db_path_ready: bool = False
    network_reachable: bool = False
    disk_free_mb: int | None = Field(default=None, ge=0)
    gpu_available: bool = False


class SupportedClankEntry(BaseModel):
    """Per-Clank local support declaration on this machine."""

    model_config = ConfigDict(extra="forbid")

    clank_id: str = Field(..., min_length=1, pattern=r"^[a-z][a-z0-9-]*$")
    max_fallback_level: FallbackLevel = FallbackLevel.LEVEL_0
    local_runtime_ready: bool = False
    secrets_ready: bool = False
    state_strategy_defined: bool = False
    fencing_supported: bool = False
    last_verified_at: datetime | None = None
    notes: str | None = None


class MachineCapabilityReport(BaseModel):
    """Full machine capability registry entry."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default=MACHINE_CONTRACT_VERSION, min_length=1)
    machine_id: str = Field(..., min_length=1)
    platform: str = Field(..., description="windows | macos | linux")
    architecture: str | None = None
    hostname: str | None = None
    capabilities: MachineCapabilities = Field(default_factory=MachineCapabilities)
    supported_clanks: list[SupportedClankEntry] = Field(default_factory=list)
    last_verified_at: datetime | None = None
    extensions: dict[str, Any] = Field(default_factory=dict)

    def clank_entry(self, clank_id: str) -> SupportedClankEntry | None:
        for entry in self.supported_clanks:
            if entry.clank_id == clank_id:
                return entry
        return None

    def can_fallback(self, clank_id: str, level: FallbackLevel) -> bool:
        entry = self.clank_entry(clank_id)
        if entry is None or not entry.local_runtime_ready:
            return False
        order = list(FallbackLevel)
        return order.index(entry.max_fallback_level) >= order.index(level)
