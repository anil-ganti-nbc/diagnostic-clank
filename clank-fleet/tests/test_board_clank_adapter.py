"""Hermetic Board 613c3a1 schema-projection tests; no workstation live DB.

The fixture spells native observer columns independently. Unqueried domain
tables have only a placeholder column; live proof separately validates the
complete canonical schema, integrity and governed snapshot manifest.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from clank_runtime.contracts.capabilities import validate_capability_states
from clank_runtime.contracts.enums import OperationalState, SourceHealthStatus

from clank_fleet.adapters.board_clank import BoardClankAdapter
from clank_fleet.adapters.factory import build_default_registry
from clank_fleet.registry.core import FleetRegistry

NOW = datetime(2026, 10, 2, 12, tzinfo=UTC)
RECENT = "2026-10-02T11:00:00+00:00"
OLD = "2026-09-23T21:08:00+00:00"
SOURCES = (
    ("banana-pi-product", "banana-pi"),
    ("hardkernel-odroid-product", "hardkernel-odroid"),
    ("orange-pi-product", "orange-pi"),
    ("pine64-product", "pine64"),
    ("radxa-product", "radxa"),
    ("raspberry-pi-product", "raspberry-pi"),
)
DOMAIN_TABLES = (
    "vendors",
    "board_families",
    "socs",
    "boards",
    "board_revisions",
    "board_variants",
    "canonical_observations",
    "observation_occurrences",
    "current_entity_observations",
    "notifications",
    "delivery_policy",
    "board_classifications",
    "novelty_evidence",
    "price_observations",
    "software_support",
)
SCHEMA = """
CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT, name TEXT);
INSERT INTO schema_migrations VALUES(1,'t','001'),(2,'t','002'),(3,'t','003');
CREATE TABLE sources(source_key TEXT PRIMARY KEY, vendor TEXT, plane TEXT, authority TEXT,
    enabled INTEGER, promotion_state TEXT, registered_state TEXT);
CREATE TABLE collector_runs(run_id TEXT PRIMARY KEY, source_key TEXT, collector_key TEXT,
    started_at TEXT, finished_at TEXT, status TEXT, fixture_scenario TEXT, error TEXT);
CREATE TABLE processed_run_receipts(run_id TEXT PRIMARY KEY, source_key TEXT,
    receipt_hash TEXT, accepted_at TEXT, observation_count INTEGER, event_count INTEGER);
CREATE TABLE source_baselines(source_key TEXT PRIMARY KEY, baseline_run_id TEXT,
    established_at TEXT, observation_count INTEGER);
CREATE TABLE run_errors(error_id INTEGER PRIMARY KEY, run_id TEXT, source_key TEXT,
    message TEXT, created_at TEXT);
CREATE TABLE events(event_id INTEGER PRIMARY KEY, event_key TEXT UNIQUE, event_type TEXT,
    source_key TEXT, run_id TEXT REFERENCES collector_runs(run_id), baseline_silent INTEGER,
    payload_json TEXT, created_at TEXT, code_revision TEXT);
CREATE TABLE diagnostic_conditions(condition_key TEXT PRIMARY KEY, source_key TEXT,
    plane TEXT, diagnostic_type TEXT, entity_key TEXT, reason TEXT, state_hash TEXT,
    status TEXT, first_observed_at TEXT, first_run_id TEXT, last_observed_at TEXT,
    last_run_id TEXT, resolved_at TEXT, resolved_run_id TEXT, open_occurrences INTEGER,
    total_occurrences INTEGER, transition_count INTEGER);
CREATE TABLE diagnostic_sightings(sighting_id INTEGER PRIMARY KEY,
    condition_key TEXT REFERENCES diagnostic_conditions(condition_key), run_id TEXT,
    source_key TEXT, observed_at TEXT, state_hash TEXT, emitted_event_key TEXT);
"""


@pytest.fixture
def board_db(tmp_path: Path) -> Path:
    db = tmp_path / "board.db"
    with sqlite3.connect(db) as con:
        con.executescript(SCHEMA)
        for table in DOMAIN_TABLES:
            con.execute(f"CREATE TABLE {table}(fixture_placeholder TEXT)")
        con.executemany(
            "INSERT INTO sources VALUES (?,?,'PRODUCT','FIRST_PARTY_CANONICAL',0,"
            "'EXPERIMENTAL','REGISTERED')",
            SOURCES,
        )
    return db


def _adapter(db: Path) -> BoardClankAdapter:
    return BoardClankAdapter(db_path=db, observed_at=NOW)


def _run(
    db: Path,
    run_id: str = "r1",
    source: str = "raspberry-pi-product",
    stamp: str = RECENT,
    status: str = "accepted",
    receipt: bool = True,
) -> None:
    with sqlite3.connect(db) as con:
        con.execute(
            "INSERT INTO collector_runs VALUES (?,?,?,?,?,?,NULL,?)",
            (
                run_id,
                source,
                source,
                stamp,
                stamp,
                status,
                "collector rejected evidence" if status == "failed" else None,
            ),
        )
        if status == "accepted" and receipt:
            con.execute(
                "INSERT INTO processed_run_receipts VALUES (?,?,?, ?,12,4)",
                (run_id, source, "receipt-" + run_id, stamp),
            )
        if status == "failed":
            con.execute(
                "INSERT INTO run_errors(run_id,source_key,message,created_at) VALUES(?,?,?,?)",
                (run_id, source, "collector rejected evidence", stamp),
            )


def _condition(
    db: Path,
    *,
    status: str = "OPEN",
    transition_count: int = 0,
    transition: str = "opened",
    total: int = 1,
) -> None:
    with sqlite3.connect(db) as con:
        con.execute(
            "INSERT INTO diagnostic_conditions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "condition-1",
                "raspberry-pi-product",
                "PRODUCT",
                "NOVELTY_UNRESOLVED",
                "rpi:unknown",
                "ambiguous model",
                "state-a",
                status,
                OLD,
                "r1",
                RECENT,
                "r1",
                RECENT if status == "RESOLVED" else None,
                "r1" if status == "RESOLVED" else None,
                0 if status == "RESOLVED" else total,
                total,
                transition_count,
            ),
        )
        con.execute(
            "INSERT INTO diagnostic_sightings VALUES(1,?,?,?,?,?,?)",
            ("condition-1", "r1", "raspberry-pi-product", RECENT, "state-a", "e1"),
        )
        con.execute(
            "INSERT INTO events VALUES(1,'e1',?,'raspberry-pi-product','r1',1,?,?,?)",
            (
                "DIAGNOSTIC_RESOLVED" if status == "RESOLVED" else "NOVELTY_UNRESOLVED",
                json.dumps({"transition": transition}),
                RECENT,
                "historical-event-revision",
            ),
        )


def _all(adapter: BoardClankAdapter) -> dict:
    return {
        name: getattr(adapter, name)()
        for name in (
            "identity",
            "capabilities",
            "status",
            "health",
            "last_run",
            "capability_states",
            "schema_revision",
            "code_revision",
            "recent_runs",
            "source_summary",
            "diagnostic_summary",
            "observer_evidence",
        )
    }


def test_exact_identity_six_method_core_and_version_namespaces(board_db: Path) -> None:
    adapter = _adapter(board_db)
    desc = adapter.identity()
    assert desc.clank_id == "board-clank"
    assert desc.release_channel.value == "experimental"
    assert desc.contract_version == "0.1.0-v3"
    for name in ("identity", "capabilities", "status", "health", "last_run", "capability_states"):
        assert callable(getattr(adapter, name))
    assert adapter.observer_evidence()["observer_contract_version"] == "0.2"
    assert adapter.observer_evidence()["payload_version"] == "1.0"


@pytest.mark.parametrize("horizon", (float("nan"), float("inf"), -float("inf"), 0, -1, True, "24"))
def test_invalid_freshness_policy_rejected(board_db: Path, horizon) -> None:
    with pytest.raises(ValueError, match="finite positive"):
        BoardClankAdapter(db_path=board_db, execution_freshness_hours=horizon)


def test_naive_observation_clock_rejected(board_db: Path) -> None:
    with pytest.raises(ValueError, match="timezone"):
        BoardClankAdapter(db_path=board_db, observed_at=datetime(2026, 10, 2))


def test_no_collection_scheduler_delivery_or_closure_authority(board_db: Path) -> None:
    adapter = _adapter(board_db)
    caps = adapter.capabilities()
    for field in (
        "supports_manual_run",
        "supports_pause",
        "supports_resume",
        "supports_delivery_accounting",
        "supports_replay",
        "supports_local_fallback",
    ):
        assert getattr(caps, field) is False
    for method in (
        "collect",
        "run",
        "pause",
        "resume",
        "send",
        "schedule",
        "enable_source",
        "promote",
        "resolve_condition",
        "migrate",
        "restore",
    ):
        assert not hasattr(adapter, method)
    assert all(value is False for value in adapter.observer_evidence()["authority"].values())
    states = adapter.capability_states()
    assert validate_capability_states(states) == []
    assert states["scheduler_trace"]["state"] == "unsupported_by_policy"
    assert states["delivery"]["state"] == "unsupported_by_policy"
    assert states["survivability"]["state"] == "unknown_or_unverified"
    assert "no deployed runtime" not in states["survivability"]["evidence"]


def test_missing_database_unknown_without_creation(tmp_path: Path) -> None:
    db = tmp_path / "absent.db"
    result = _all(_adapter(db))
    assert result["status"].operational_state is OperationalState.UNKNOWN
    assert result["health"].overall_status is OperationalState.UNKNOWN
    assert result["last_run"]["supported"] is True
    assert result["last_run"]["evidence_state"] == "UNKNOWN"
    assert result["source_summary"] == []
    assert result["diagnostic_summary"] == {"conditions": [], "sightings_total": "UNKNOWN"}
    assert result["observer_evidence"]["availability"]["state"] == "UNKNOWN"
    assert not db.exists()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "table",
    (
        "schema_migrations",
        "sources",
        "collector_runs",
        "events",
        "processed_run_receipts",
        "source_baselines",
        "diagnostic_conditions",
        "diagnostic_sightings",
        "run_errors",
        "boards",
    ),
)
def test_missing_native_table_fails_closed(board_db: Path, table: str) -> None:
    with sqlite3.connect(board_db) as con:
        con.execute(f"DROP TABLE {table}")
    result = _all(_adapter(board_db))
    assert result["status"].operational_state is OperationalState.UNKNOWN
    assert result["health"].overall_status is OperationalState.UNKNOWN
    assert result["observer_evidence"]["availability"]["state"] == "UNKNOWN"
    if table in {"schema_migrations", "sources"}:
        assert result["source_summary"] == []
    else:
        assert len(result["source_summary"]) == 6
    if table in {"schema_migrations", "diagnostic_conditions", "diagnostic_sightings"}:
        assert result["diagnostic_summary"]["sightings_total"] == "UNKNOWN"


@pytest.mark.parametrize("version", (None, 1, 2, 4, 99))
def test_schema_mismatch_unknown_never_migrates(board_db: Path, version: int | None) -> None:
    with sqlite3.connect(board_db) as con:
        con.execute("DELETE FROM schema_migrations")
        if version is not None:
            con.execute("INSERT INTO schema_migrations VALUES (?,'t','other')", (version,))
    before = board_db.read_bytes()
    adapter = _adapter(board_db)
    assert adapter.status().operational_state is OperationalState.UNKNOWN
    assert adapter.schema_revision() == (str(version) if version is not None else None)
    assert adapter.observer_evidence()["availability"]["state"] == "UNKNOWN"
    assert board_db.read_bytes() == before


def test_missing_native_column_unknown(board_db: Path) -> None:
    with sqlite3.connect(board_db) as con:
        con.execute("ALTER TABLE events DROP COLUMN code_revision")
    assert _adapter(board_db).observer_evidence()["availability"]["state"] == "UNKNOWN"


@pytest.mark.parametrize("data", (b"not sqlite", b""))
def test_corrupt_or_empty_database_unknown(tmp_path: Path, data: bytes) -> None:
    db = tmp_path / "bad.db"
    db.write_bytes(data)
    assert _adapter(db).status().operational_state is OperationalState.UNKNOWN
    assert db.read_bytes() == data


@pytest.mark.parametrize("suffix", ("-wal", "-shm", "-journal"))
def test_sidecar_snapshots_rejected(board_db: Path, suffix: str) -> None:
    sidecar = Path(str(board_db) + suffix)
    sidecar.write_bytes(b"evidence sidecar")
    assert _adapter(board_db).observer_evidence()["availability"]["state"] == "UNKNOWN"
    assert sidecar.read_bytes() == b"evidence sidecar"


def test_wal_header_snapshot_rejected(board_db: Path) -> None:
    con = sqlite3.connect(board_db)
    con.execute("PRAGMA journal_mode=WAL")
    con.close()
    assert _adapter(board_db).observer_evidence()["availability"]["state"] == "UNKNOWN"


def test_foreign_key_failure_unknown(board_db: Path) -> None:
    with sqlite3.connect(board_db) as con:
        con.execute("INSERT INTO diagnostic_sightings VALUES(1,'missing','r','s','t','h',NULL)")
    assert _adapter(board_db).observer_evidence()["availability"]["state"] == "UNKNOWN"


def test_all_six_disabled_experimental_roster_exact_native_shape(board_db: Path) -> None:
    adapter = _adapter(board_db)
    summary = adapter.source_summary()
    assert summary == [
        dict(
            source_key=key,
            vendor=vendor,
            plane="PRODUCT",
            authority="FIRST_PARTY_CANONICAL",
            enabled=0,
            promotion_state="EXPERIMENTAL",
            registered_state="REGISTERED",
        )
        for key, vendor in SOURCES
    ]
    assert all(entry.status is SourceHealthStatus.UNKNOWN for entry in adapter.health().sources)
    assert adapter.capability_states()["collection"]["state"] == "supported_unconfigured"
    assert all(row["latest_attempt"] is None for row in adapter.observer_evidence()["sources"])


def test_schema_and_accepted_run_do_not_establish_health(board_db: Path) -> None:
    _run(board_db)
    adapter = _adapter(board_db)
    assert adapter.schema_revision() == "3"
    assert adapter.status().operational_state is OperationalState.UNKNOWN
    assert adapter.health().overall_status is OperationalState.UNKNOWN
    last = adapter.last_run()
    assert last["supported"] is True
    assert last["execution_result"] == "APPLICATION_SUCCESS"
    assert last["clock"] == "native_run_row"
    assert last["derived_from"] == "collector_runs"
    evidence = next(
        row
        for row in adapter.observer_evidence()["sources"]
        if row["source_key"] == "raspberry-pi-product"
    )
    assert evidence["latest_accepted_run"]["run_id"] == "r1"
    assert evidence["latest_accepted_receipt"]["receipt_hash"] == "receipt-r1"


def test_accepted_run_does_not_fabricate_receipt(board_db: Path) -> None:
    _run(board_db, receipt=False)
    row = next(
        row
        for row in _adapter(board_db).observer_evidence()["sources"]
        if row["source_key"] == "raspberry-pi-product"
    )
    assert row["latest_accepted_run"]["status"] == "accepted"
    assert row["latest_accepted_receipt"] is None


def test_latest_failure_mixed_sources_and_recovery(board_db: Path) -> None:
    _run(board_db, "ok", "raspberry-pi-product")
    _run(board_db, "bad", "orange-pi-product", status="failed")
    adapter = _adapter(board_db)
    assert adapter.status().operational_state is OperationalState.DEGRADED
    by_id = {s.source_id: s for s in adapter.health().sources}
    assert by_id["orange-pi-product"].status is SourceHealthStatus.FAILED
    assert by_id["pine64-product"].status is SourceHealthStatus.UNKNOWN
    assert by_id["raspberry-pi-product"].status is SourceHealthStatus.UNKNOWN
    assert adapter.last_run()["execution_result"] == "APPLICATION_FAILED"
    bad = next(
        row
        for row in adapter.observer_evidence()["sources"]
        if row["source_key"] == "orange-pi-product"
    )
    assert bad["latest_accepted_receipt"] is None
    assert bad["recent_errors"][0]["message"] == "collector rejected evidence"
    _run(board_db, "recovered", "orange-pi-product", "2026-10-02T11:10:00+00:00")
    assert adapter.health().overall_status is OperationalState.UNKNOWN
    assert all(s.status is not SourceHealthStatus.FAILED for s in adapter.health().sources)


@pytest.mark.parametrize("stamp", (OLD, "2030-01-01T00:00:00+00:00", "bad", "2026-10-02T11:00:00"))
def test_stale_or_invalid_child_clock_does_not_create_current_health(
    board_db: Path, stamp: str
) -> None:
    _run(board_db, stamp=stamp, status="failed")
    adapter = _adapter(board_db)
    assert adapter.status().is_stale is True
    assert adapter.health().overall_status is OperationalState.UNKNOWN
    assert adapter.health().freshness in {"stale", "unknown"}


def test_fresh_transport_does_not_refresh_child_execution(board_db: Path, tmp_path: Path) -> None:
    _run(board_db, stamp=OLD)
    copy = tmp_path / "fresh-transport.db"
    with (
        sqlite3.connect(board_db.resolve().as_uri() + "?mode=ro", uri=True) as source,
        sqlite3.connect(copy) as destination,
    ):
        source.backup(destination)
    adapter = _adapter(copy)
    assert adapter.status().is_stale is True
    assert adapter.health().freshness == "stale"
    assert adapter.last_run()["finished_at"] == OLD


@pytest.mark.parametrize(
    "status,transition,count",
    (
        ("OPEN", "opened", 0),
        ("RESOLVED", "resolved", 1),
        ("OPEN", "reappeared", 2),
    ),
)
def test_native_diagnostic_shape_identity_and_transition_evidence(
    board_db: Path,
    status: str,
    transition: str,
    count: int,
) -> None:
    _run(board_db)
    _condition(board_db, status=status, transition=transition, transition_count=count)
    adapter = _adapter(board_db)
    summary = adapter.diagnostic_summary()
    assert summary == {
        "conditions": [
            {
                "source_key": "raspberry-pi-product",
                "diagnostic_type": "NOVELTY_UNRESOLVED",
                "status": status,
                "reason": "ambiguous model",
                "n": 1,
            }
        ],
        "sightings_total": 1,
    }
    diag = adapter.observer_evidence()["diagnostics"]
    assert diag["conditions"][0]["condition_key"] == "condition-1"
    assert diag["conditions"][0]["status"] == status
    assert diag["conditions"][0]["transition_count"] == count
    assert diag["sightings"][0]["emitted_event_key"] == "e1"
    assert (
        json.loads(diag["recent_transition_events"][0]["payload_json"])["transition"] == transition
    )
    assert adapter.health().overall_status is OperationalState.UNKNOWN
    assert all(s.status is not SourceHealthStatus.FAILED for s in adapter.health().sources)


def test_repeated_diagnostic_sighting_is_not_repeated_novelty_or_mutation(board_db: Path) -> None:
    _run(board_db)
    _condition(board_db, total=2)
    with sqlite3.connect(board_db) as con:
        con.execute(
            "INSERT INTO diagnostic_sightings VALUES(2,'condition-1','r1',"
            "'raspberry-pi-product',?,'state-a',NULL)",
            (RECENT,),
        )
    before = board_db.read_bytes()
    first = _adapter(board_db).observer_evidence()
    second = _adapter(board_db).observer_evidence()
    assert first == second
    assert first["diagnostics"]["sightings_total"] == 2
    assert len(first["diagnostics"]["recent_transition_events"]) == 1
    assert first["events"]["counts"] == [
        {"event_type": "NOVELTY_UNRESOLVED", "baseline_silent": 1, "n": 1}
    ]
    assert board_db.read_bytes() == before


def test_missing_sightings_preserves_native_condition_evidence(board_db: Path) -> None:
    _run(board_db)
    _condition(board_db)
    with sqlite3.connect(board_db) as con:
        con.execute("DROP TABLE diagnostic_sightings")
    adapter = _adapter(board_db)
    assert adapter.diagnostic_summary()["conditions"][0]["status"] == "OPEN"
    assert adapter.diagnostic_summary()["sightings_total"] == "UNKNOWN"
    assert adapter.observer_evidence()["availability"]["state"] == "UNKNOWN"
    assert adapter.health().overall_status is OperationalState.UNKNOWN


def test_diagnostic_detail_limit_declares_truncation(board_db: Path) -> None:
    _run(board_db)
    _condition(board_db)
    with sqlite3.connect(board_db) as con:
        con.executemany(
            "INSERT INTO diagnostic_sightings VALUES(?,'condition-1','r1',"
            "'raspberry-pi-product',?,'state-a',NULL)",
            ((index, RECENT) for index in range(2, 1002)),
        )
    adapter = _adapter(board_db)
    assert adapter.diagnostic_summary()["sightings_total"] == 1001
    evidence = adapter.observer_evidence()["diagnostics"]
    assert evidence["sightings_total"] == 1001
    assert evidence["sightings_truncated"] is True
    assert len(evidence["sightings"]) == 1000
    assert evidence["sightings"][0]["sighting_id"] == 2


def test_event_source_and_deployed_revisions_stay_distinct(board_db: Path) -> None:
    _run(board_db)
    _condition(board_db)
    adapter = _adapter(board_db)
    revisions = adapter.observer_evidence()["revisions"]
    assert adapter.code_revision() == "historical-event-revision"
    assert revisions["latest_event"]["code_revision"] == "historical-event-revision"
    assert revisions["child_source_revision"] == "UNKNOWN"
    assert revisions["child_deployed_revision"] == "UNKNOWN"
    assert adapter.status().extensions["deployment_state"] == "UNKNOWN"


def test_read_only_all_methods_hash_no_sidecars_no_synthetic_rows(board_db: Path) -> None:
    _run(board_db)
    _condition(board_db)
    before = hashlib.sha256(board_db.read_bytes()).hexdigest()
    names = sorted(p.name for p in board_db.parent.iterdir())
    _all(_adapter(board_db))
    assert hashlib.sha256(board_db.read_bytes()).hexdigest() == before
    assert sorted(p.name for p in board_db.parent.iterdir()) == names
    with sqlite3.connect(board_db.resolve().as_uri() + "?mode=ro", uri=True) as con:
        assert con.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert con.execute("PRAGMA foreign_key_check").fetchall() == []
        assert con.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM diagnostic_sightings").fetchone()[0] == 1


def test_sqlite_connections_are_readonly_immutable_queryonly(board_db: Path, monkeypatch) -> None:
    real_connect = sqlite3.connect
    calls = []
    statements = []

    def tracked_connect(database, **kwargs):
        calls.append((database, kwargs))
        con = real_connect(database, **kwargs)
        con.set_trace_callback(statements.append)
        return con

    monkeypatch.setattr(sqlite3, "connect", tracked_connect)
    result = _all(_adapter(board_db))
    assert calls, result["observer_evidence"]["availability"]
    assert all("mode=ro&immutable=1" in uri and kwargs["uri"] for uri, kwargs in calls)
    assert all(sql.upper().startswith(("SELECT", "PRAGMA")) for sql in statements)
    assert "PRAGMA query_only=ON" in statements


def test_uri_special_characters_do_not_change_database_identity(board_db: Path) -> None:
    special = board_db.with_name("board # snapshot %.db")
    special.write_bytes(board_db.read_bytes())
    assert len(_adapter(special).source_summary()) == 6


def test_baseline_evidence_preserved_without_market_novelty_inference(board_db: Path) -> None:
    _run(board_db)
    with sqlite3.connect(board_db) as con:
        con.execute(
            "INSERT INTO source_baselines VALUES('raspberry-pi-product','r1',?,12)", (RECENT,)
        )
    evidence = _adapter(board_db).observer_evidence()
    source = next(row for row in evidence["sources"] if row["source_key"] == "raspberry-pi-product")
    assert source["baseline"] == {
        "source_key": "raspberry-pi-product",
        "baseline_run_id": "r1",
        "established_at": RECENT,
        "observation_count": 12,
    }
    assert "novelty" not in source["baseline"]


def test_factory_board_opt_in_preserves_existing_five(board_db: Path) -> None:
    existing = build_default_registry()
    with_board = build_default_registry(board_db=board_db)
    assert "board-clank" not in existing.list_ids()
    assert set(with_board.list_ids()) == set(existing.list_ids()) | {"board-clank"}
    assert len(existing.list_ids()) == 5
    adapter = with_board.get("board-clank").adapter
    assert adapter.db_path == board_db
    assert adapter.capabilities().supports_manual_run is False


def test_duplicate_registry_clank_rejected(board_db: Path) -> None:
    registry = FleetRegistry()
    registry.register(_adapter(board_db))
    with pytest.raises(ValueError, match="duplicate clank_id"):
        registry.register(_adapter(board_db))
