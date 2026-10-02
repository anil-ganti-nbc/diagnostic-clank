"""The six-method core is sufficient; optional evidence is never fabricated."""
from __future__ import annotations

import logging
from pathlib import Path

from clank_fleet.adapters.board_clank import BoardClankAdapter
from clank_fleet.adapters.factory import build_default_registry
from clank_fleet.registry.core import (
    FleetAdapter, FleetRegistry, SupportsDiagnosticSummary,
    SupportsObserverEvidence, SupportsSourceSummary, SupportsTelemetry,
)
from clank_runtime.contracts.adapter import AdapterCapabilities, AdapterDescriptor, AdapterStatus
from clank_runtime.contracts.health import HealthPayload
from clank_runtime.contracts.telemetry import TelemetryEnvelope


class CoreOnly:
    def identity(self) -> AdapterDescriptor:
        return AdapterDescriptor(clank_id="core-only", clank_version="1")

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities()

    def status(self) -> AdapterStatus:
        return AdapterStatus(clank_id="core-only")

    def health(self) -> HealthPayload:
        return HealthPayload(clank_id="core-only")

    def last_run(self) -> None:
        return None

    def capability_states(self) -> dict[str, dict[str, str]]:
        return {}


class WithSummary(CoreOnly):
    def source_summary(self) -> list[dict[str, str]]:
        return [{"source_key": "native", "promotion_state": "EXPERIMENTAL"}]


class WithTelemetry(CoreOnly):
    def __init__(self) -> None:
        self.limit: int | None = None

    def telemetry(self, *, limit: int = 20) -> list[TelemetryEnvelope]:
        self.limit = limit
        return []


# These assignments are also checked by the dedicated static-contract probe.
CORE_ASSIGNMENT: FleetAdapter = CoreOnly()
SUMMARY_ASSIGNMENT: SupportsSourceSummary = WithSummary()
TELEMETRY_ASSIGNMENT: SupportsTelemetry = WithTelemetry()


def test_core_only_is_valid_without_optional_surfaces(caplog) -> None:
    adapter = CoreOnly()
    assert isinstance(adapter, FleetAdapter)
    assert not isinstance(adapter, SupportsTelemetry)
    assert not isinstance(adapter, SupportsSourceSummary)
    registry = FleetRegistry()
    registry.register(adapter)
    with caplog.at_level(logging.ERROR):
        assert registry.safe_telemetry("core-only") == []
        assert registry.safe_sources("core-only") == []
    assert not caplog.records  # Unsupported is not an adapter failure.
    assert registry.safe_status("core-only") == adapter.status()


def test_optional_summary_is_detected_and_consumed_verbatim() -> None:
    adapter = WithSummary()
    assert isinstance(adapter, FleetAdapter)
    assert isinstance(adapter, SupportsSourceSummary)
    registry = FleetRegistry()
    registry.register(adapter)
    assert registry.safe_sources("core-only") == adapter.source_summary()


def test_optional_telemetry_passes_limit() -> None:
    adapter = WithTelemetry()
    registry = FleetRegistry()
    registry.register(adapter)
    assert registry.safe_telemetry("core-only", limit=7) == []
    assert adapter.limit == 7


def test_raising_optional_extension_is_isolated(caplog) -> None:
    class BrokenSummary(CoreOnly):
        def source_summary(self) -> list[dict[str, str]]:
            raise RuntimeError("native failure")

    registry = FleetRegistry()
    registry.register(BrokenSummary())
    assert registry.safe_sources("core-only") == []
    assert "adapter_sources_failed" in caplog.text
    assert registry.safe_status("core-only").clank_id == "core-only"


def test_noncallable_extension_is_not_invoked(caplog) -> None:
    adapter = CoreOnly()
    setattr(adapter, "telemetry", 123)
    setattr(adapter, "source_summary", 123)
    registry = FleetRegistry()
    registry.register(adapter)
    assert registry.safe_sources("core-only") == []
    assert registry.safe_telemetry("core-only") == []
    assert not caplog.records


def test_board_and_legacy_protocol_boundaries(tmp_path: Path) -> None:
    defaults = build_default_registry()
    assert defaults.list_ids() == [
        "feature-phone-clank", "korean-tech-wire", "oem-radar",
        "smartphone-clank", "watch-clank",
    ]
    assert all(isinstance(defaults.get(cid).adapter, FleetAdapter) for cid in defaults.list_ids())
    adapter = BoardClankAdapter(db_path=tmp_path / "absent.db")
    assert isinstance(adapter, FleetAdapter)
    assert isinstance(adapter, SupportsSourceSummary)
    assert isinstance(adapter, SupportsDiagnosticSummary)
    assert isinstance(adapter, SupportsObserverEvidence)
    assert not isinstance(adapter, SupportsTelemetry)
    assert not hasattr(adapter, "telemetry")
    assert adapter.capabilities().supports_telemetry is False
    opted_in = build_default_registry(board_db=tmp_path / "absent.db")
    assert opted_in.list_ids() == ["board-clank", *defaults.list_ids()]
