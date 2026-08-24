"""Smartwatch adapter fixture tests (truthful operational stage).

The fixture below reproduces the REAL restored-DB schema observed
2026-08-24 (runs/collector_health/schema_version, exact column names) -
not an arbitrary/synthetic table set. Verifies the adapter reports real
operational evidence without inventing vocabulary the schema doesn't
express (e.g. no DEGRADED/BLOCKED_ZERO from a plain 0/1 `healthy` column).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from clank_fleet.adapters.smartwatch_clank import (
    LIVE_SCHEMA_VALIDATION,
    SmartwatchClankAdapter,
)
from clank_runtime.contracts.enums import OperationalState, SourceHealthStatus


@pytest.fixture()
def fixture_db(tmp_path: Path) -> Path:
    db = tmp_path / "smartwatch-clank.sqlite3"
    con = sqlite3.connect(db)
    con.execute("""CREATE TABLE runs (
        id INTEGER PRIMARY KEY, collector TEXT, started_at TEXT,
        finished_at TEXT, healthy INTEGER, observation_count INTEGER,
        warning TEXT, error TEXT)""")
    con.execute("""CREATE TABLE collector_health (
        collector TEXT, healthy INTEGER, observed_count INTEGER,
        previous_count INTEGER, warning TEXT, error TEXT, checked_at TEXT)""")
    con.execute("CREATE TABLE schema_version (id INTEGER, version INTEGER, updated_at TEXT)")
    con.execute(
        "INSERT INTO runs VALUES (1,'samsung_support_in','2026-08-24T05:50:19Z',"
        "'2026-08-24T05:50:24Z',1,57,NULL,NULL)")
    con.execute(
        "INSERT INTO runs VALUES (2,'garmin_official_news','2026-08-24T05:49:00Z',"
        "'2026-08-24T05:49:05Z',0,0,NULL,'HTTPError 403')")
    con.execute(
        "INSERT INTO collector_health VALUES "
        "('samsung_support_in',1,57,57,NULL,NULL,'2026-08-24T05:50:24Z')")
    con.execute(
        "INSERT INTO collector_health VALUES "
        "('garmin_official_news',0,0,NULL,NULL,'HTTPError 403','2026-08-24T05:49:05Z')")
    con.execute("INSERT INTO schema_version VALUES (1,2,'2026-08-18T12:37:49Z')")
    con.commit()
    con.close()
    return db


def test_identity_and_capabilities_are_honest(fixture_db):
    adapter = SmartwatchClankAdapter(db_path=fixture_db)
    desc = adapter.identity()
    assert desc.clank_id == "smartwatch-clank"
    caps = adapter.capabilities()
    assert caps.supports_health is True
    assert caps.supports_last_run is True
    assert LIVE_SCHEMA_VALIDATION == "MAPPED"


def test_missing_db_is_unknown_never_failed(tmp_path):
    adapter = SmartwatchClankAdapter(db_path=tmp_path / "nope.sqlite3")
    status = adapter.status()
    assert status.operational_state == OperationalState.UNKNOWN
    health = adapter.health()
    assert health.overall_status == OperationalState.UNKNOWN
    assert health.warnings


def test_store_inventory_reflects_real_tables(fixture_db):
    adapter = SmartwatchClankAdapter(db_path=fixture_db)
    inv = adapter.store_inventory()
    assert inv["available"] is True
    assert inv["live_schema_validation"] == "MAPPED"
    assert inv["tables"]["runs"] == 2
    assert inv["tables"]["collector_health"] == 2


def test_last_run_reports_real_latest_run_ordered_by_finished_at(fixture_db):
    adapter = SmartwatchClankAdapter(db_path=fixture_db)
    lr = adapter.last_run()
    assert lr["supported"] is True
    # samsung_support_in finished later than garmin_official_news
    assert lr["collector"] == "samsung_support_in"
    assert lr["status"] == "ok"
    assert lr["run_kind"] is None  # no baseline/run-kind column in this schema


def test_health_maps_two_valued_schema_without_inventing_states(fixture_db):
    adapter = SmartwatchClankAdapter(db_path=fixture_db)
    health = adapter.health()
    assert health.overall_status == OperationalState.DEGRADED  # 1 of 2 sources failed
    statuses = {s.source_id: s.status for s in health.sources}
    assert statuses["samsung_support_in"] == SourceHealthStatus.OK
    assert statuses["garmin_official_news"] == SourceHealthStatus.FAILED
    # schema has no DEGRADED/BLOCKED_ZERO/ZERO_ITEMS column - never invented
    assert SourceHealthStatus.DEGRADED not in statuses.values()


def test_schema_revision_reads_real_table(fixture_db):
    adapter = SmartwatchClankAdapter(db_path=fixture_db)
    assert adapter.schema_revision() == 2
