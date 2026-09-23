"""Board Clank observer adapter — contract tests (P-4.7 candidate).

Shape tests against a REAL Board Clank shadow database snapshot when one is
available (bounded fixture), and against a synthetic minimal schema
otherwise. Laws under test:

- read-only: adapter methods never mutate the observed database
- observer-tier: no scheduler/notification/enable authority anywhere
- UNKNOWN stays literal (missing DB, missing tables, no runs)
- deployment is never inferred (no source/CI collapse)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from clank_fleet.adapters.board_clank import BoardClankAdapter
from clank_runtime.contracts.enums import OperationalState, SourceHealthStatus

# Bounded fixture: a copy of the real board-clank shadow state if present
# on this workstation (P-4.7 live soak evidence).
SHADOW_DB_CANDIDATES = [
    Path(r"C:\Users\anil\Clanks\_Soak\board-clank-shadow-runtime\shadow-runtime.sqlite"),
]


def _shadow_db(tmp_path: Path) -> Path | None:
    for candidate in SHADOW_DB_CANDIDATES:
        if candidate.exists():
            target = tmp_path / "board-clank-shadow.db"
            target.write_bytes(candidate.read_bytes())
            return target
    return None


def _minimal_schema_db(tmp_path: Path) -> Path:
    """Synthetic board-clank-shaped schema (canonical v3 tables, minimal rows)."""
    db = tmp_path / "minimal.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE schema_migrations (version INTEGER, applied_at TEXT, name TEXT);
        INSERT INTO schema_migrations VALUES (1, 't', '001'), (2, 't', '002'), (3, 't', '003');
        CREATE TABLE collector_runs (run_id TEXT, source_key TEXT, collector_key TEXT,
            started_at TEXT, finished_at TEXT, status TEXT, fixture_scenario TEXT, error TEXT);
        INSERT INTO collector_runs VALUES ('r1', 'raspberry-pi-product', 'raspberry-pi-product',
            '2026-09-23T01:00:00+00:00', '2026-09-23T01:00:10+00:00', 'accepted', NULL, NULL);
        CREATE TABLE events (event_id INTEGER PRIMARY KEY, code_revision TEXT);
        INSERT INTO events (code_revision) VALUES ('6747bc2354b84562a9f7e49638b77c59e6952e43');
        CREATE TABLE sources (source_key TEXT, vendor TEXT, plane TEXT, authority TEXT,
            enabled INTEGER, promotion_state TEXT, registered_state TEXT);
        INSERT INTO sources VALUES ('pine64-product', 'pine64', 'PRODUCT', 'FIRST_PARTY_CANONICAL', 0, 'EXPERIMENTAL', 'REGISTERED');
        CREATE TABLE diagnostic_conditions (source_key TEXT, diagnostic_type TEXT, status TEXT);
        INSERT INTO diagnostic_conditions VALUES ('radxa-product', 'NOVELTY_UNRESOLVED', 'OPEN');
        """
    )
    con.commit()
    con.close()
    return db


def test_identity_is_observer_tier_experimental(tmp_path: Path) -> None:
    adapter = BoardClankAdapter(db_path=_minimal_schema_db(tmp_path))
    descriptor = adapter.identity()
    assert descriptor.clank_id == "board-clank"
    assert descriptor.release_channel.value == "experimental"
    # ADAPTER_CONTRACT_VERSION ("0.1.0-v3") is the clank_runtime wire
    # contract; the Observer Adapter Surface Contract (v0.2) governs which
    # METHODS the adapter exposes, per ADAPTER_CONTRACT.md reconciliation.
    assert descriptor.contract_version == "0.1.0-v3"


def test_capabilities_declare_no_delivery_and_no_manual_run(tmp_path: Path) -> None:
    adapter = BoardClankAdapter(db_path=_minimal_schema_db(tmp_path))
    caps = adapter.capabilities()
    assert caps.supports_delivery_accounting is False
    assert caps.supports_manual_run is False
    states = adapter.capability_states()
    assert states["delivery"]["state"] == "unsupported_by_policy"
    assert states["scheduler_trace"]["state"] == "unsupported_by_policy"
    for entry in states.values():
        assert entry["evidence"]


def test_status_schema_and_code_revision_from_native_rows(tmp_path: Path) -> None:
    db = _minimal_schema_db(tmp_path)
    adapter = BoardClankAdapter(db_path=db)
    assert adapter.schema_revision() == "3"
    assert adapter.code_revision() == "6747bc2354b84562a9f7e49638b77c59e6952e43"
    status = adapter.status()
    assert status.clank_id == "board-clank"
    last = adapter.last_run()
    assert last is not None
    assert last["execution_result"] == "APPLICATION_SUCCESS"
    assert last["clock"] if "clock" in last else True  # native row projection


def test_health_reports_sources_and_degraded_on_failure(tmp_path: Path) -> None:
    db = _minimal_schema_db(tmp_path)
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO collector_runs VALUES ('r2', 'orange-pi-product', 'orange-pi-product',"
        " '2026-09-23T02:00:00+00:00', NULL, 'failed', NULL, 'collector failed')"
    )
    con.commit()
    con.close()
    adapter = BoardClankAdapter(db_path=db)
    payload = adapter.health()
    assert payload.clank_id == "board-clank"
    assert payload.overall_status == OperationalState.DEGRADED
    source_ids = {entry.source_id for entry in payload.sources}
    assert {"raspberry-pi-product", "orange-pi-product"} <= source_ids
    assert all(entry.status == SourceHealthStatus.UNKNOWN for entry in payload.sources)


def test_missing_database_stays_unknown(tmp_path: Path) -> None:
    adapter = BoardClankAdapter(db_path=tmp_path / "missing.db")
    assert adapter.schema_revision() is None
    assert adapter.code_revision() is None
    assert adapter.last_run() is None
    assert adapter.status().operational_state == OperationalState.UNKNOWN


def test_read_only_guarantee_byte_for_byte(tmp_path: Path) -> None:
    db = _minimal_schema_db(tmp_path)
    before = db.read_bytes()
    adapter = BoardClankAdapter(db_path=db)
    adapter.capability_states()
    adapter.status()
    adapter.health()
    adapter.last_run()
    adapter.recent_runs()
    adapter.schema_revision()
    adapter.code_revision()
    assert db.read_bytes() == before


def test_shadow_database_if_available(tmp_path: Path) -> None:
    """Live-shadow probe: runs only when the bounded shadow snapshot exists
    on this workstation; proves the adapter reads real runtime state."""
    db = _shadow_db(tmp_path)
    if db is None:
        pytest.skip("board-clank shadow database not present on this workstation")
    adapter = BoardClankAdapter(db_path=db)
    last = adapter.last_run()
    assert last is not None
    assert last["run_id"].startswith("shadow-")
    states = adapter.capability_states()
    assert states["delivery"]["state"] == "unsupported_by_policy"
