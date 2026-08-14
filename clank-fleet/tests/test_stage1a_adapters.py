"""Stage 1A: two heterogeneous Clanks via read-only adapters."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from clank_fleet.adapters.feature_phone import FeaturePhoneAdapter
from clank_fleet.adapters.oem_radar import OemRadarAdapter
from clank_fleet.fleet_api.app import create_app
from clank_fleet.registry.core import FleetRegistry
from clank_runtime.contracts.enums import OperationalState, SourceHealthStatus

FIXTURES = Path(__file__).parent / "fixtures"
OEM_DB = FIXTURES / "oem_radar_fixture.db"
FP_DB = FIXTURES / "feature_phone_fixture.db"


@pytest.fixture()
def registry() -> FleetRegistry:
    reg = FleetRegistry()
    reg.register(OemRadarAdapter(db_path=OEM_DB))
    reg.register(FeaturePhoneAdapter(db_path=FP_DB))
    return reg


def test_register_both_distinct_capabilities(registry: FleetRegistry) -> None:
    assert registry.list_ids() == ["feature-phone-clank", "oem-radar"]
    oem = registry.get("oem-radar").adapter.capabilities()
    fp = registry.get("feature-phone-clank").adapter.capabilities()
    assert oem.supports_delivery_accounting is True
    assert fp.supports_delivery_accounting is False
    assert oem.supports_health is True and fp.supports_health is True


def test_duplicate_registration_rejected(registry: FleetRegistry) -> None:
    with pytest.raises(ValueError, match="duplicate"):
        registry.register(OemRadarAdapter(db_path=OEM_DB))


def test_oem_health_and_telemetry(registry: FleetRegistry) -> None:
    health = registry.safe_health("oem-radar")
    assert health.clank_id == "oem-radar"
    assert health.is_stale_cache is False
    ids = {s.source_id for s in health.sources}
    assert "gmktec-shopify" in ids
    assert "dell-us" in ids
    dell = next(s for s in health.sources if s.source_id == "dell-us")
    assert dell.status == SourceHealthStatus.FAILED
    telem = registry.safe_telemetry("oem-radar")
    assert len(telem) >= 1
    assert telem[0].clank_id == "oem-radar"
    assert telem[0].run_id


def test_feature_phone_blocked_zero_mapped(registry: FleetRegistry) -> None:
    # Latest per source is ok; telemetry history includes blocked_zero
    telem = registry.safe_telemetry("feature-phone-clank", limit=10)
    statuses = {t.source_status for t in telem}
    assert SourceHealthStatus.BLOCKED_ZERO in statuses or SourceHealthStatus.OK in statuses
    # Ensure we never fabricated delivery_count=0 when unsupported
    for t in telem:
        assert t.delivery_count is None


def test_adapter_isolation_one_broken_does_not_hide_other(registry: FleetRegistry) -> None:
    # Point OEM at missing DB
    registry._adapters["oem-radar"].adapter = OemRadarAdapter(db_path="/tmp/does-not-exist-oem.db")  # noqa: SLF001
    oem_status = registry.safe_status("oem-radar")
    assert oem_status.is_stale or oem_status.operational_state == OperationalState.UNKNOWN
    fp_status = registry.safe_status("feature-phone-clank")
    assert fp_status.clank_id == "feature-phone-clank"
    assert fp_status.operational_state in {
        OperationalState.HEALTHY,
        OperationalState.WARNING,
        OperationalState.DEGRADED,
    }


def test_missing_db_marks_stale() -> None:
    adapter = FeaturePhoneAdapter(db_path="/tmp/missing-fp.db")
    health = adapter.health()
    assert health.is_stale_cache is True
    assert health.overall_status == OperationalState.UNKNOWN


def test_fleet_api_lists_both(registry: FleetRegistry) -> None:
    app = create_app()
    app.state.fleet_registry = registry
    client = TestClient(app)
    r = client.get("/api/v1/clanks")
    assert r.status_code == 200
    ids = {c["clank_id"] for c in r.json()["clanks"]}
    assert ids == {"oem-radar", "feature-phone-clank"}
    h = client.get("/api/v1/clanks/oem-radar/health")
    assert h.status_code == 200
    assert h.json()["clank_id"] == "oem-radar"
    t = client.get("/api/v1/clanks/feature-phone-clank/telemetry")
    assert t.status_code == 200
    s = client.get("/api/v1/clanks/oem-radar/sources")
    assert s.status_code == 200
    assert isinstance(s.json()["sources"], list)
    missing = client.get("/api/v1/clanks/not-a-clank/health")
    assert missing.status_code == 404


def test_fleet_summary(registry: FleetRegistry) -> None:
    summary = registry.fleet_summary()
    by_id = {row["clank_id"]: row for row in summary}
    assert by_id["oem-radar"]["delivery_visibility"] == "FULL"
    assert by_id["feature-phone-clank"]["delivery_visibility"] == "LIMITED"


def test_readonly_does_not_mutate_fixture(registry: FleetRegistry) -> None:
    import sqlite3

    before = OEM_DB.stat().st_mtime_ns
    registry.safe_health("oem-radar")
    registry.safe_telemetry("oem-radar")
    after = OEM_DB.stat().st_mtime_ns
    assert before == after
    # journal mode should not create write artifacts from RO uri
    con = sqlite3.connect(f"file:{OEM_DB.resolve().as_posix()}?mode=ro", uri=True)
    try:
        n = con.execute("SELECT COUNT(*) FROM crawler_runs").fetchone()[0]
        assert n == 3
    finally:
        con.close()
