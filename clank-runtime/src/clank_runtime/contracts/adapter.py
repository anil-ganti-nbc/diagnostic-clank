"""Fleet adapter protocol and capability declaration.

Existing Clanks integrate through adapters. They do NOT rewrite collectors
or internal schemas. Capabilities are explicit; Fleet never assumes an
unsupported operation works.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from clank_runtime.contracts.enums import FallbackLevel, OperationalState, ReleaseChannel
from clank_runtime.version import ADAPTER_CONTRACT_VERSION


class AdapterCapabilities(BaseModel):
    """What this adapter can do. All default False except identity/status."""

    model_config = ConfigDict(extra="forbid")

    supports_identity: bool = True
    supports_status: bool = True
    supports_health: bool = False
    supports_last_run: bool = False
    supports_manual_run: bool = False
    supports_pause: bool = False
    supports_resume: bool = False
    supports_logs: bool = False
    supports_telemetry: bool = False
    supports_delivery_accounting: bool = False
    supports_backup_status: bool = False
    supports_version: bool = True
    supports_replay: bool = False
    supports_local_fallback: bool = False
    max_fallback_level: FallbackLevel = FallbackLevel.LEVEL_0


class AdapterDescriptor(BaseModel):
    """Static descriptor returned by identity()/capabilities()."""

    model_config = ConfigDict(extra="forbid")

    contract_version: str = Field(default=ADAPTER_CONTRACT_VERSION, min_length=1)
    clank_id: str = Field(..., min_length=1, pattern=r"^[a-z][a-z0-9-]*$")
    clank_version: str = Field(..., min_length=1)
    release_channel: ReleaseChannel = ReleaseChannel.EXPERIMENTAL
    capabilities: AdapterCapabilities = Field(default_factory=AdapterCapabilities)
    display_name: str | None = None
    description: str | None = None


class AdapterStatus(BaseModel):
    """Live or last-known status from an adapter."""

    model_config = ConfigDict(extra="forbid")

    clank_id: str
    operational_state: OperationalState = OperationalState.UNKNOWN
    release_channel: ReleaseChannel | None = None
    last_run_at: datetime | None = None
    last_success_at: datetime | None = None
    version: str | None = None
    location: str | None = Field(
        default=None,
        description="nas | local_fallback | unavailable | …",
    )
    message: str | None = None
    is_stale: bool = False
    observed_at: datetime | None = None
    extensions: dict[str, Any] = Field(default_factory=dict)


class UnsupportedOperationError(Exception):
    """Raised when Fleet requests an operation the adapter does not support."""

    def __init__(self, clank_id: str, operation: str) -> None:
        self.clank_id = clank_id
        self.operation = operation
        super().__init__(f"adapter {clank_id!r} does not support operation {operation!r}")


@runtime_checkable
class ClankAdapter(Protocol):
    """Minimum adapter surface. Methods beyond identity/status are optional
    and must be gated by AdapterCapabilities.
    """

    def identity(self) -> AdapterDescriptor: ...

    def status(self) -> AdapterStatus: ...

    def capabilities(self) -> AdapterCapabilities: ...
