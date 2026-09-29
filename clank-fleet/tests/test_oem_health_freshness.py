"""OEM Radar health must distinguish persisted source evidence from query time."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from clank_fleet.adapters.oem_radar import OemRadarAdapter
from clank_runtime.contracts.enums import OperationalState


def _db_with_runs(tmp_path, statuses: tuple[str, ...]):
    path = tmp_path / "radar.db"
    with sqlite3.connect(path) as con:
        con.execute(
            "CREATE TABLE crawler_runs ("
            "id INTEGER PRIMARY KEY, source_key TEXT, status TEXT, "
            "finished_at TEXT, stats_json TEXT)"
        )
        for run_id, status in enumerate(statuses, start=1):
            con.execute(
                "INSERT INTO crawler_runs "
                "(id, source_key, status, finished_at) VALUES (?, ?, ?, ?)",
                (run_id, f"source-{run_id}", status,
                 f"2026-08-14T10:{run_id:02d}:00+00:00"),
            )
    return path


def test_oem_health_last_attempt_comes_from_latest_native_run(tmp_path) -> None:
    db = _db_with_runs(tmp_path, ("ok", "failed"))
    before = datetime.now(UTC)
    health = OemRadarAdapter(db_path=db).health()
    after = datetime.now(UTC)

    assert health.last_attempt_at == datetime(2026, 8, 14, 10, 2, tzinfo=UTC)
    assert before <= health.observed_at <= after
    assert health.last_attempt_at != health.observed_at
    assert health.overall_status == OperationalState.DEGRADED


def test_oem_health_no_run_does_not_invent_attempt(tmp_path) -> None:
    health = OemRadarAdapter(db_path=_db_with_runs(tmp_path, ())).health()
    assert health.last_attempt_at is None
    assert health.overall_status == OperationalState.WARNING


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        (("degraded",), OperationalState.DEGRADED),
        (("unrecognized",), OperationalState.UNKNOWN),
        (("ok", "unrecognized"), OperationalState.WARNING),
        (("ok", "degraded"), OperationalState.DEGRADED),
        (("failed", "failed"), OperationalState.FAILED),
    ],
)
def test_oem_health_does_not_upgrade_non_ok_sources(
    tmp_path, statuses: tuple[str, ...], expected: OperationalState
) -> None:
    health = OemRadarAdapter(db_path=_db_with_runs(tmp_path, statuses)).health()
    assert health.overall_status == expected
