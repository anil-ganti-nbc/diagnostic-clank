"""Smartwatch adapter fixture tests (schema-introspection stage).

P4-G6: the adapter must produce real-state-compatible, UNKNOWN-honest
output against a fixture DB WITHOUT inventing schema semantics, and
Motherclank must onboard it via registry alone (zero core edits).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from clank_fleet.adapters.smartwatch_clank import (
    LIVE_SCHEMA_VALIDATION,
    SmartwatchClankAdapter,
)
from clank_runtime.contracts.enums import OperationalState


@pytest.fixture()
def fixture_db(tmp_path: Path) -> Path:
    """Synthetic store with deliberately arbitrary table names: the adapter
    must introspect whatever exists without assuming domain meaning."""
    db = tmp_path / "smartwatch-clank.sqlite3"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE some_future_run_table (id INTEGER PRIMARY KEY)")
    con.execute("INSERT INTO some_future_run_table VALUES (1)")
    con.execute("CREATE TABLE unrelated (x TEXT)")
    con.commit()
    con.close()
    return db


def test_identity_and_capabilities_are_honest(fixture_db):
    adapter = SmartwatchClankAdapter(db_path=fixture_db)
    desc = adapter.identity()
    assert desc.clank_id == "smartwatch-clank"
    caps = adapter.capabilities()
    assert caps.supports_health is False
    assert caps.supports_last_run is False
    assert LIVE_SCHEMA_VALIDATION == "BLOCKED"


def test_missing_db_is_unknown_never_failed(tmp_path):
    adapter = SmartwatchClankAdapter(db_path=tmp_path / "nope.sqlite3")
    status = adapter.status()
    assert status.operational_state == OperationalState.UNKNOWN
    health = adapter.health()
    assert health.overall_status == OperationalState.UNKNOWN
    assert health.warnings


def test_store_inventory_counts_without_semantic_claims(fixture_db):
    adapter = SmartwatchClankAdapter(db_path=fixture_db)
    inv = adapter.store_inventory()
    assert inv["available"] is True
    assert inv["live_schema_validation"] == "BLOCKED"
    assert inv["tables"] == {"some_future_run_table": 1, "unrelated": 0}


def test_last_run_refuses_to_guess():
    adapter = SmartwatchClankAdapter(db_path="unused")
    lr = adapter.last_run()
    assert lr["supported"] is False
    assert lr["finished_at"] is None and lr["status"] is None
