"""Motherclank M1.5 — adapter truth-cleanup regressions (diagnostic-clank side).

Defects being locked shut (discovered by Motherclank M1 on real state):
  D-M1.5a smartphone last_run() ordered by UUID-string id -> arbitrary row
          (false-STALE; inverse ordering risk = false-HEALTHY)
  D-M1.5b unmapped status vocabularies (watch SUCCESS/PARTIAL, smartphone
          success/degraded) collapsed to UNKNOWN — honest but lossy;
          mapping now explicit WITHOUT ever upgrading ambiguous values.

Layered validation: hermetic fixtures + real host copies via REAL_STATE_DIR.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from clank_fleet.adapters.feature_phone import _map_run_status
from clank_fleet.adapters.smartphone_clank import SmartphoneClankAdapter
from clank_fleet.adapters.watch_clank import WatchClankAdapter
from clank_runtime.contracts.enums import SourceHealthStatus

REAL_STATE_DIR = Path(__import__("os").environ.get("REAL_STATE_DIR", "")) \
    if __import__("os").environ.get("REAL_STATE_DIR") else None


# ---------------------------------------------------------------------------
# 1. Status mapping: never upgrades degraded/unknown/garbage to healthy
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("ok", "ok"),
    ("success", "ok"),            # smartphone native
    ("SUCCESS", "ok"),            # watch native (case-insensitive)
    ("failed", "failed"),
    ("error", "failed"),
    ("blocked_zero_result", "blocked_zero"),
    ("degraded", "degraded"),
    ("DEGRADED", "degraded"),
    ("partial", "degraded"),      # watch native: partial success is NOT ok
    ("PARTIAL", "degraded"),
])
def test_mapped_vocabularies(raw, expected):
    assert _map_run_status(raw).value == expected


@pytest.mark.parametrize("raw", [
    "", None, "unknown", "totally_novel_status", "success-ish", "  ",
    "SUCCESSFUL_BUT_LIES", "0", "ok ",
])
def test_unmapped_or_ambiguous_values_stay_unknown(raw):
    """Mapping must not upgrade unrecognized evidence to OK."""
    assert _map_run_status(raw) == SourceHealthStatus.UNKNOWN


def test_mapping_never_returns_ok_for_non_affirmative_inputs():
    for raw in ("degraded", "partial", "unknown", "blocked_zero_result",
                "failure", "timeout", None):
        assert _map_run_status(raw) != SourceHealthStatus.OK


# ---------------------------------------------------------------------------
# 2. UUID-order trap: timestamp ordering must select the true latest run
# ---------------------------------------------------------------------------

@pytest.fixture()
def uuid_trap_db(tmp_path):
    """Lexicographically LARGEST uuid holds the OLDER finished_at; a smaller
    uuid holds the NEWEST. id-DESC ordering must lose to finished_at DESC."""
    p = tmp_path / "smartphone_clank.db"
    con = sqlite3.connect(p)
    con.executescript(
        """
        CREATE TABLE alembic_version (version_num TEXT);
        CREATE TABLE collector_run_metrics (
            id TEXT PRIMARY KEY, collector_name TEXT, source_name TEXT,
            started_at TEXT, finished_at TEXT, duration_ms INT, status TEXT,
            pages_requested INT, pages_fetched INT, bytes_downloaded INT,
            http_requests INT, http_failures INT, parser_failures INT,
            candidates_found INT, valid_devices INT, new_devices INT,
            updated_devices INT, evidence_added INT, meaningful_changes INT,
            alerts_sent INT, maintenance_alerts_sent INT, cache_hits INT,
            cache_misses INT, peak_rss_kb INT, cpu_time_ms INT, notes TEXT,
            meta TEXT, resighted INT, run_reason TEXT);
        """
    )
    con.execute("INSERT INTO alembic_version VALUES ('0007_wave1_baseline_state')")
    rows = [
        # lexicographically LAST uuid -> OLD timestamp (the M1 trap row)
        ("ffffffff-ffff-ffff-ffff-ffffffffffff", "google_store_phones",
         "google_store", "2026-08-18 01:20:53.416223",
         "2026-08-18 01:20:53.416223", "success"),
        # lexicographically SMALL uuid -> genuinely newest run, DEGRADED
        ("aaaaaaaa-0000-0000-0000-000000000001", "google_store_phones",
         "google_store", "2026-08-22 06:40:00.000000",
         "2026-08-22 06:53:11.484374", "degraded"),
    ]
    for r in rows:
        con.execute(
            """
            INSERT INTO collector_run_metrics
                (id, collector_name, source_name, started_at, finished_at,
                 status, run_reason)
            VALUES (?, ?, ?, ?, ?, ?, 'production_scheduled')
            """,
            r,
        )
    con.commit(); con.close()
    return p


def test_last_run_ignores_uuid_lexical_order(uuid_trap_db):
    a = SmartphoneClankAdapter(db_path=uuid_trap_db)
    last = a.last_run()
    assert last is not None
    assert last["finished_at"].startswith("2026-08-22"), \
        "id-desc picked the wrong row — must order by finished_at"
    assert last["status"] == "degraded"


def test_telemetry_ordering_matches_recency(uuid_trap_db):
    a = SmartphoneClankAdapter(db_path=uuid_trap_db)
    envs = a.telemetry(limit=5)
    assert envs[0].finished_at.isoformat().startswith("2026-08-22")
    assert envs[0].source_status == SourceHealthStatus.DEGRADED


def test_health_rollup_reflects_true_latest_not_trap_row(uuid_trap_db):
    a = SmartphoneClankAdapter(db_path=uuid_trap_db)
    h = a.health()
    statuses = [s.status for s in h.sources]
    assert SourceHealthStatus.DEGRADED in statuses


# ---------------------------------------------------------------------------
# 3. Real-state validation (opt-in): adapters agree with SQL truth
# ---------------------------------------------------------------------------

@pytest.mark.skipif(REAL_STATE_DIR is None or not Path(REAL_STATE_DIR or ".").exists(),
                    reason="REAL_STATE_DIR not provided")
class TestRealStateTruth:
    def test_smartphone_last_run_equals_sql_max_finished_at(self):
        db = Path(REAL_STATE_DIR) / "smartphone_clank.db"  # type: ignore[operator]
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        sql_latest = con.execute(
            "SELECT collector_name, status, finished_at FROM collector_run_metrics "
            "WHERE finished_at=(SELECT MAX(finished_at) FROM collector_run_metrics)"
        ).fetchone()
        con.close()
        a = SmartphoneClankAdapter(db_path=db)
        last = a.last_run()
        assert last["finished_at"] == sql_latest[2], \
            f"adapter {last['finished_at']} != sql max {sql_latest[2]}"
        assert last["collector_name" if False else "source_id"] == sql_latest[0]

    def test_watch_statuses_no_longer_all_unknown(self):
        db = Path(REAL_STATE_DIR) / "watch_clank.db"  # type: ignore[operator]
        h = WatchClankAdapter(db_path=db).health()
        mapped = [s.status.value for s in h.sources]
        assert len(mapped) >= 10
        unknown_ratio = mapped.count("unknown") / len(mapped)
        assert unknown_ratio < 0.5, \
            f"SUCCESS/PARTIAL mapping should resolve most watch sources: {mapped}"

    def test_smartphone_statuses_resolved(self):
        db = Path(REAL_STATE_DIR) / "smartphone_clank.db"  # type: ignore[operator]
        h = SmartphoneClankAdapter(db_path=db).health()
        mapped = [s.status.value for s in h.sources]
        assert len(mapped) >= 8
        assert "ok" in mapped, "real fleet has successful collectors"
        unknown_ratio = mapped.count("unknown") / len(mapped)
        assert unknown_ratio < 0.25
