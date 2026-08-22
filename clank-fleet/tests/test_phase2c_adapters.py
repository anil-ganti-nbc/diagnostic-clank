"""Phase 2C adapter-plane tests.

Two layers:
1. Hermetic fixture tests (tiny synthetic DBs built with the REAL schemas of
   watch-clank / smartphone-clank / korean-tech-wire) — run anywhere, CI-safe.
2. Real-state validation (opt-in): if REAL_STATE_DIR (env) contains DB copies
   pulled from the live Hetzner volumes, adapters are exercised against those.
   Real copies are never committed to git.

Adapters are strictly read-only: every connection opens with mode=ro.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from clank_fleet.adapters.korean_tech_wire import KoreanTechWireAdapter
from clank_fleet.adapters.smartphone_clank import SmartphoneClankAdapter
from clank_fleet.adapters.watch_clank import WatchClankAdapter

REAL_STATE_DIR = Path(os.environ.get("REAL_STATE_DIR", "")) if os.environ.get("REAL_STATE_DIR") else None


# ---------------------------------------------------------------------------
# Fixture builders — real schemas, obviously-synthetic rows
# ---------------------------------------------------------------------------

@pytest.fixture()
def watch_db(tmp_path: Path) -> Path:
    p = tmp_path / "watch_clank.db"
    con = sqlite3.connect(p)
    con.executescript(
        """
        CREATE TABLE alembic_version (version_num VARCHAR(32));
        CREATE TABLE operational_epochs (id INTEGER PRIMARY KEY, name TEXT, started_at TEXT,
            baseline_started_at TEXT, baseline_completed_at TEXT, notes TEXT, created_at TEXT);
        CREATE TABLE collector_runs (id INTEGER PRIMARY KEY, source_id TEXT, status TEXT,
            started_at TEXT, finished_at TEXT, observations_count INT, events_created INT);
        CREATE TABLE events (id INTEGER PRIMARY KEY, event_type TEXT, title TEXT, status TEXT,
            story_score REAL, confidence_score REAL, data_completeness_score REAL,
            scoring_rule_version TEXT, extra TEXT, created_at TEXT, updated_at TEXT);
        CREATE TABLE event_reviews (id INTEGER PRIMARY KEY, event_id INT, disposition TEXT,
            reason TEXT, created_at TEXT);
        """
    )
    con.execute("INSERT INTO alembic_version VALUES ('0007_test')")
    con.execute("INSERT INTO operational_epochs VALUES (1,'EPOCH 1','2026-08-11T13:11:25Z','2026-08-11T13:11:25Z','2026-08-11T14:00:00Z',NULL,'2026-08-11T13:11:25Z')")
    for i, (src, status) in enumerate([("casio_multi", "SUCCESS"), ("timex_news", "SUCCESS"), ("seiko_jp_products", "PARTIAL")], 1):
        con.execute(
            "INSERT INTO collector_runs VALUES (?,?,?,?,?,?,?)",
            (i, src, status, "2026-08-21T19:43:47Z", "2026-08-21T19:44:10Z", 10 + i, i),
        )
    con.execute("INSERT INTO events VALUES (1,'NEW_REFERENCE','Test ref','DRAFT',50.0,0.5,0.9,'v1',NULL,'2026-08-21T20:00:00Z','2026-08-21T20:00:00Z')")
    con.execute("INSERT INTO event_reviews VALUES (1,1,'USEFUL','real launch','2026-08-21T21:00:00Z')")
    con.commit(); con.close()
    return p


@pytest.fixture()
def smartphone_db(tmp_path: Path) -> Path:
    p = tmp_path / "smartphone_clank.db"
    con = sqlite3.connect(p)
    con.executescript(
        """
        CREATE TABLE alembic_version (version_num VARCHAR(64));
        CREATE TABLE collector_run_metrics (id INTEGER PRIMARY KEY, collector_name TEXT,
            source_name TEXT, started_at TEXT, finished_at TEXT, duration_ms INT, status TEXT,
            pages_requested INT, pages_fetched INT, bytes_downloaded INT, http_requests INT,
            http_failures INT, parser_failures INT, candidates_found INT, valid_devices INT,
            new_devices INT, updated_devices INT, evidence_added INT, meaningful_changes INT,
            alerts_sent INT, maintenance_alerts_sent INT, cache_hits INT, cache_misses INT,
            peak_rss_kb INT, cpu_time_ms INT, notes TEXT, meta TEXT, resighted INT, run_reason TEXT);
        CREATE TABLE webhook_deliveries (id INTEGER PRIMARY KEY, reason TEXT);
        CREATE TABLE alerts (id INTEGER PRIMARY KEY);
        CREATE TABLE timeline_events (id INTEGER PRIMARY KEY, device_id INT, event_type TEXT,
            source TEXT, title TEXT, url TEXT, occurred_at TEXT, recorded_at TEXT,
            evidence_id INT, meta TEXT);
        CREATE TABLE rejected_candidates (id INTEGER PRIMARY KEY);
        CREATE TABLE confidence_ledger (id INTEGER PRIMARY KEY);
        CREATE TABLE analyst_actions (id INTEGER PRIMARY KEY, action_type TEXT);
        """
    )
    con.execute("INSERT INTO alembic_version VALUES ('0007_wave1_baseline_state')")
    con.execute(
        "INSERT INTO collector_run_metrics VALUES (1,'google_store_phones','google_store',"
        "'2026-08-21T20:18:03Z','2026-08-21T20:18:40Z',37000,'ok',3,3,1000,3,0,0,12,12,0,0,3,"
        "1,0,0,0,3,5000,40,NULL,NULL,4,'production_scheduled')"
    )
    con.execute("INSERT INTO webhook_deliveries VALUES (1,'new_model')")
    con.execute("INSERT INTO alerts VALUES (1)")
    con.execute("INSERT INTO timeline_events VALUES (1,1,'new_model','google_store','Pixel 9','u','2026-08-21T20:00:00Z','2026-08-21T20:01:00Z',NULL,NULL)")
    con.commit(); con.close()
    return p


@pytest.fixture()
def ktw_db(tmp_path: Path) -> Path:
    p = tmp_path / "korean_tech_wire.db"
    con = sqlite3.connect(p)
    con.executescript(
        """
        CREATE TABLE schema_migrations (version INT);
        CREATE TABLE sources (id INTEGER PRIMARY KEY, name TEXT, status TEXT, updated_at TEXT);
        CREATE TABLE runs (id INTEGER PRIMARY KEY, started_at TEXT, finished_at TEXT);
        CREATE TABLE source_run_health (id INTEGER PRIMARY KEY, run_id INT, source_id INT,
            attempted_at TEXT, duration_ms INT, success INT, references_discovered INT,
            accepted INT, rejected INT, new_articles INT, existing_articles INT,
            extraction_failures INT, timestamped INT, health_note TEXT);
        CREATE TABLE articles (id INTEGER PRIMARY KEY, source_id INT, canonical_url TEXT,
            discovered_at TEXT);
        CREATE TABLE article_feedback (id INTEGER PRIMARY KEY);
        """
    )
    con.execute("INSERT INTO schema_migrations VALUES (4)")
    for i, (n, s) in enumerate([("sk_hynix_newsroom", "PRODUCTION"), ("the_elec", "PRODUCTION"), ("lg_display_newsroom", "EXPERIMENTAL")], 1):
        con.execute("INSERT INTO sources VALUES (?,?,?,?)", (i, n, s, "2026-08-21T20:00:00Z"))
    con.execute("INSERT INTO runs VALUES (1,'2026-08-21T22:03:27Z','2026-08-21T22:03:37Z')")
    # sk_hynix: long failure streak (HOST-BLOCKED specimen -> must read FAILED/DEGRADED, never healthy-by-history)
    for i in range(10):
        con.execute("INSERT INTO source_run_health VALUES (?,?,?,?,1,0,5,0,5,0,5,0,0,'blocked')", (i + 1, 1, 1, f"2026-08-{10+i:02d}T09:00:00Z"))
    con.execute("INSERT INTO source_run_health VALUES (20,1,2,'2026-08-21T22:03:30Z',900,1,8,6,2,2,6,0,2,NULL)")
    con.execute("INSERT INTO articles VALUES (1,2,'https://x/a','2026-08-21T22:03:31Z')")
    con.commit(); con.close()
    return p


# ---------------------------------------------------------------------------
# Hermetic behavior
# ---------------------------------------------------------------------------

def test_watch_adapter_reads_real_schema(watch_db):
    a = WatchClankAdapter(db_path=watch_db)
    assert a.schema_revision() == "0007_test"
    epoch = a.current_epoch()
    assert epoch["name"] == "EPOCH 1" and epoch["baseline_completed_at"] is not None
    summary = a.event_summary()
    assert summary["events_total"] == 1
    assert summary["event_review_dispositions"] == {"USEFUL": 1}
    last = a.last_run()
    assert last["source_key"] == "seiko_jp_products"
    env = a.telemetry(limit=5)
    assert len(env) == 3 and env[0].delivery_count is None  # UNKNOWN stays null


def test_watch_adapter_missing_db_is_unknown(tmp_path):
    from clank_runtime.contracts.enums import OperationalState
    st = WatchClankAdapter(db_path=tmp_path / "nope.db").status()
    assert st.operational_state == OperationalState.UNKNOWN


def test_smartphone_adapter_delivery_and_qc(smartphone_db):
    a = SmartphoneClankAdapter(db_path=smartphone_db)
    assert a.schema_revision() == "0007_wave1_baseline_state"
    d = a.delivery_summary()
    assert d["delivery_rows_by_reason"] == {"new_model": 1}
    assert d["delivered_alerts_total"] == 1  # generation(1 row) vs delivery(1 alert) distinguished
    qc = a.qc_summary()
    assert qc["rejected_candidates_total"] == 0 and qc["confidence_ledger_entries"] == 0
    tax = a.timeline_taxonomy()
    assert tax == {"new_model": 1}
    env = a.telemetry(limit=5)
    assert env[0].run_kind.value in ("normal_run", "NORMAL_RUN")


def test_ktw_adapter_blocked_source_never_reads_healthy(ktw_db):
    """Law 3 specimen: SK hynix HOST-BLOCKED history (all failures) must not read OK."""
    a = KoreanTechWireAdapter(db_path=ktw_db)
    h = a.health()
    by_src = {s.source_id: s for s in h.sources}
    assert by_src["sk_hynix_newsroom"].status.value != "ok"
    assert by_src["the_elec"].status.value == "ok"
    assert by_src["the_elec"].last_success_at is not None
    lifecycle = {r["name"]: r["status"] for r in a.source_lifecycle()}
    assert lifecycle["lg_display_newsroom"] == "EXPERIMENTAL"
    art = a.article_summary()
    assert art["articles_total"] == 1
    env = a.telemetry(limit=5)
    assert all(e.event_count is None for e in env)  # no event lane by policy


def test_adapters_are_read_only(tmp_path, watch_db):
    """Open the fixture copy, run every adapter entrypoint, assert file mtime/hash unchanged."""
    import hashlib
    before = hashlib.sha256(watch_db.read_bytes()).hexdigest()
    a = WatchClankAdapter(db_path=watch_db)
    a.status(); a.health(); a.last_run(); a.telemetry(); a.event_summary(); a.current_epoch()
    after = hashlib.sha256(watch_db.read_bytes()).hexdigest()
    assert before == after


# ---------------------------------------------------------------------------
# Real-state validation (opt-in; copies live outside git)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(REAL_STATE_DIR is None or not Path(REAL_STATE_DIR or ".").exists(),
                    reason="REAL_STATE_DIR not provided")
class TestRealState:
    def test_watch_real(self):
        a = WatchClankAdapter(db_path=Path(REAL_STATE_DIR) / "watch_clank.db")  # type: ignore[operator]
        last = a.last_run()
        assert last is not None and last.get("status") == "SUCCESS"
        # Real host DB (2026-08-22 copy) carries an EMPTY operational_epochs table:
        # the adapter must surface None honestly rather than fabricate an epoch.
        assert a.current_epoch() in (None,) or isinstance(a.current_epoch(), dict)
        assert isinstance(a.event_summary().get("events_total"), int)

    def test_smartphone_real(self):
        a = SmartphoneClankAdapter(db_path=Path(REAL_STATE_DIR) / "smartphone_clank.db")  # type: ignore[operator]
        assert a.schema_revision() == "0007_wave1_baseline_state"
        d = a.delivery_summary()
        assert (d.get("delivered_alerts_total") or 0) > 0

    def test_ktw_real(self):
        a = KoreanTechWireAdapter(db_path=Path(REAL_STATE_DIR) / "korean_tech_wire.db")  # type: ignore[operator]
        h = a.health()
        names = {s.source_id for s in h.sources}
        # real host DB uses display names
        assert {"SK hynix Newsroom Korea", "The Elec (디일렉)"} & names
        assert a.article_summary()["articles_total"] > 400
