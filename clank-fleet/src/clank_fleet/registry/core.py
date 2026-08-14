"""Fleet registry core.

One broken adapter must not hide other Clanks (Fleet-level isolation).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from clank_runtime.contracts.adapter import (
    AdapterCapabilities,
    AdapterDescriptor,
    AdapterStatus,
    UnsupportedOperationError,
)
from clank_runtime.contracts.enums import OperationalState
from clank_runtime.contracts.health import HealthPayload
from clank_runtime.contracts.telemetry import TelemetryEnvelope

log = logging.getLogger("clank_fleet.registry")


@runtime_checkable
class FleetAdapter(Protocol):
    """Stage 1A read-oriented adapter protocol."""

    def identity(self) -> AdapterDescriptor: ...

    def capabilities(self) -> AdapterCapabilities: ...

    def status(self) -> AdapterStatus: ...

    def health(self) -> HealthPayload: ...

    def last_run(self) -> dict[str, Any] | None: ...

    def telemetry(self, *, limit: int = 20) -> list[TelemetryEnvelope]: ...

    def source_summary(self) -> list[dict[str, Any]]: ...


@dataclass
class RegisteredClank:
    clank_id: str
    adapter: FleetAdapter
    enabled: bool = True
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class FleetRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, RegisteredClank] = {}

    def register(self, adapter: FleetAdapter, *, enabled: bool = True) -> None:
        identity = adapter.identity()
        clank_id = identity.clank_id
        if clank_id in self._adapters:
            raise ValueError(f"duplicate clank_id: {clank_id}")
        self._adapters[clank_id] = RegisteredClank(
            clank_id=clank_id, adapter=adapter, enabled=enabled
        )
        log.info("adapter_registered clank_id=%s", clank_id)

    def list_ids(self) -> list[str]:
        return sorted(self._adapters)

    def get(self, clank_id: str) -> RegisteredClank:
        if clank_id not in self._adapters:
            raise KeyError(clank_id)
        return self._adapters[clank_id]

    def safe_status(self, clank_id: str) -> AdapterStatus:
        try:
            reg = self.get(clank_id)
            if not reg.enabled:
                return AdapterStatus(
                    clank_id=clank_id,
                    operational_state=OperationalState.PAUSED,
                    message="adapter disabled",
                    observed_at=datetime.now(UTC),
                )
            return reg.adapter.status()
        except Exception as exc:  # noqa: BLE001 — isolation
            log.exception("adapter_status_failed clank_id=%s", clank_id)
            return AdapterStatus(
                clank_id=clank_id,
                operational_state=OperationalState.UNKNOWN,
                message=f"adapter error: {exc}",
                is_stale=True,
                observed_at=datetime.now(UTC),
            )

    def safe_health(self, clank_id: str) -> HealthPayload:
        try:
            reg = self.get(clank_id)
            return reg.adapter.health()
        except Exception as exc:  # noqa: BLE001
            log.exception("adapter_health_failed clank_id=%s", clank_id)
            return HealthPayload(
                clank_id=clank_id,
                overall_status=OperationalState.UNKNOWN,
                warnings=[f"adapter error: {exc}"],
                is_stale_cache=True,
                observed_at=datetime.now(UTC),
            )

    def safe_telemetry(self, clank_id: str, *, limit: int = 20) -> list[TelemetryEnvelope]:
        try:
            return self.get(clank_id).adapter.telemetry(limit=limit)
        except Exception as exc:  # noqa: BLE001
            log.exception("adapter_telemetry_failed clank_id=%s", clank_id)
            return []

    def safe_sources(self, clank_id: str) -> list[dict[str, Any]]:
        try:
            return self.get(clank_id).adapter.source_summary()
        except Exception as exc:  # noqa: BLE001
            log.exception("adapter_sources_failed clank_id=%s", clank_id)
            return []

    def fleet_summary(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for clank_id in self.list_ids():
            status = self.safe_status(clank_id)
            health = self.safe_health(clank_id)
            caps = self.get(clank_id).adapter.capabilities()
            delivery = "FULL" if caps.supports_delivery_accounting else "LIMITED"
            rows.append(
                {
                    "clank_id": clank_id,
                    "operational_state": status.operational_state.value,
                    "is_stale": status.is_stale or health.is_stale_cache,
                    "last_run_at": status.last_run_at.isoformat() if status.last_run_at else None,
                    "last_success_at": status.last_success_at.isoformat()
                    if status.last_success_at
                    else None,
                    "sources_total": len(health.sources),
                    "sources_failed": sum(
                        1
                        for s in health.sources
                        if s.status.value in {"failed", "blocked_zero", "blocked"}
                    ),
                    "delivery_visibility": delivery,
                    "message": status.message,
                }
            )
        return rows
