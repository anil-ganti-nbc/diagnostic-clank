"""Board Clank read-only Fleet adapter (P-4.7 candidate).

Observer-tier onboarding preparation against Board Clank's own declared
observer semantics (Observer Adapter Surface Contract v0.2 required core
implemented Board-side in ``board_clank.observer``). This adapter reads
Board Clank's SQLite schema only — it never duplicates Board Clank's SBC
domain logic, never mutates state (read-only URI connections), never
enables sources, schedules runs, sends notifications, or closes Board
Clank's durable diagnostic conditions.

Board Clank owns SBC domain truth. Motherclank observes it.

Schema notes (canonical from board-clank migration 001..003, schema v3):
- collector_runs: per-source attempts (status accepted/failed, error text)
- events: event plane with baseline_silent + code_revision provenance
- diagnostic_conditions / diagnostic_sightings: durable uncertainty state
- sources: roster with enabled/promotion_state (board-clank governs these;
  this adapter only reads them)
- delivery: outbox-only (notifications table, no send path) → delivery
  accounting unsupported by policy, never fabricated.

Live onboarding status: BLOCKED/UNKNOWN — the Diagnostic host (NAS) was
unreachable during the onboarding mission, so this adapter has NOT been
soaked against a live Motherclank harvest. Local contract tests cover
shape against a real Board Clank shadow database.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from clank_fleet.adapters.base import open_readonly, table_exists
from clank_runtime.contracts.adapter import (
    AdapterCapabilities,
    AdapterDescriptor,
    AdapterStatus,
)
from clank_runtime.contracts.enums import OperationalState, ReleaseChannel
from clank_runtime.contracts.health import HealthPayload, SourceHealthEntry
from clank_runtime.contracts.enums import SourceHealthStatus
from clank_runtime.version import ADAPTER_CONTRACT_VERSION

CLANK_ID = "board-clank"


class BoardClankAdapter:
    def __init__(
        self,
        *,
        db_path: Path | str,
        clank_version: str = "0.1.0",
        release_channel: str = "experimental",
    ) -> None:
        self.db_path = Path(db_path)
        self.clank_version = clank_version
        self.release_channel = release_channel

    # -- capability states --------------------------------------------------

    def capability_states(self) -> dict[str, dict[str, str]]:
        con = open_readonly(self.db_path)
        sources_state = "unknown_or_unverified"
        events_state = "unknown_or_unverified"
        continuity_state = "unknown_or_unverified"
        if con is not None:
            try:
                if table_exists(con, "sources"):
                    rows = con.execute("SELECT enabled FROM sources").fetchall()
                    enabled = sum(1 for row in rows if row["enabled"])
                    sources_state = (
                        "unsupported_by_policy" if enabled == 0 else "active"
                    )
                if table_exists(con, "events"):
                    events_state = "active"
                if table_exists(con, "processed_run_receipts"):
                    continuity_state = "active"
            finally:
                con.close()
        return {
            "collection": {
                "state": sources_state,
                "evidence": "sources roster read directly; enabled=false by policy" if sources_state == "unsupported_by_policy" else "sources roster",
            },
            "health": {"state": "active", "evidence": "collector_runs + run_errors substrate"},
            "events": {"state": events_state, "evidence": "event plane with baseline_silent taxonomy + code_revision provenance"},
            "delivery": {"state": "unsupported_by_policy", "evidence": "notifications outbox-only; no send path exists in board-clank"},
            "qc": {"state": "unsupported", "evidence": "no QC substrate in schema v3"},
            "scheduler_trace": {"state": "unsupported_by_policy", "evidence": "board-clank declares scheduler_authority NONE"},
            "continuity": {"state": continuity_state, "evidence": "processed_run_receipts + source_baselines + forward migrations"},
            "survivability": {"state": "supported_undeployed", "evidence": "verified backup/restore implemented; no deployed runtime yet"},
            "diagnostics": {"state": "active", "evidence": "diagnostic_conditions/diagnostic_sightings durable state"},
        }

    # -- identity -----------------------------------------------------------

    def identity(self) -> AdapterDescriptor:
        try:
            channel = ReleaseChannel(self.release_channel)
        except ValueError:
            channel = ReleaseChannel.EXPERIMENTAL
        return AdapterDescriptor(
            contract_version=ADAPTER_CONTRACT_VERSION,
            clank_id=CLANK_ID,
            clank_version=self.clank_version,
            release_channel=channel,
            capabilities=self.capabilities(),
            display_name="Board Clank",
            description="SBC hardware/vendor inventory and novelty intelligence (six first-party PRODUCT sources, all experimental/disabled)",
        )

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_identity=True,
            supports_status=True,
            supports_health=True,
            supports_last_run=True,
            supports_telemetry=False,
            supports_delivery_accounting=False,  # outbox-only; send path does not exist
            supports_version=True,
            supports_manual_run=False,
            supports_local_fallback=False,
        )

    # -- status -------------------------------------------------------------

    def status(self) -> AdapterStatus:
        now = datetime.now(UTC)
        if not self.db_path.exists():
            return AdapterStatus(
                clank_id=CLANK_ID,
                operational_state=OperationalState.UNKNOWN,
                message=f"database missing: {self.db_path}",
                is_stale=True,
                observed_at=now,
            )
        con = open_readonly(self.db_path)
        try:
            if con is None:
                return AdapterStatus(
                    clank_id=CLANK_ID,
                    operational_state=OperationalState.UNKNOWN,
                    message="database unreadable",
                    is_stale=True,
                    observed_at=now,
                )
            if not table_exists(con, "schema_migrations"):
                operational = OperationalState.UNKNOWN
                message = "schema marker absent"
            else:
                row = con.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
                observed = row[0] if row else None
                operational = (
                    OperationalState.HEALTHY if observed == 3 else OperationalState.UNKNOWN
                )
                message = f"schema version observed: {observed}"
            last = self.last_run()
            if last and last.get("status") == "failed":
                operational = OperationalState.DEGRADED
                message = f"last run failed: {last.get('run_id')}"
            return AdapterStatus(
                clank_id=CLANK_ID,
                operational_state=operational,
                message=message,
                is_stale=last is None,
                observed_at=now,
            )
        finally:
            con.close()

    def schema_revision(self) -> str | None:
        con = open_readonly(self.db_path)
        if con is None:
            return None
        try:
            if not table_exists(con, "schema_migrations"):
                return None
            row = con.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
            return str(row[0]) if row and row[0] is not None else None
        finally:
            con.close()

    def code_revision(self) -> str | None:
        """Board Clank stamps every event with its build revision (Fleet Law
        6). The latest accepted run's revision is the lane's code revision.
        UNKNOWN stays literal."""
        con = open_readonly(self.db_path)
        if con is None:
            return None
        try:
            if not table_exists(con, "events"):
                return None
            row = con.execute(
                "SELECT code_revision FROM events ORDER BY event_id DESC LIMIT 1"
            ).fetchone()
            return row["code_revision"] if row else None
        finally:
            con.close()

    # -- health -------------------------------------------------------------

    def health(self) -> HealthPayload:
        con = open_readonly(self.db_path)
        empty = HealthPayload(clank_id=CLANK_ID)
        if con is None:
            return empty
        try:
            if not table_exists(con, "collector_runs"):
                return empty
            source_rows = con.execute(
                """
                SELECT source_key,
                       SUM(CASE WHEN status = 'accepted' THEN 1 ELSE 0 END) AS accepted,
                       SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                       MAX(started_at) AS last_attempt
                FROM collector_runs GROUP BY source_key ORDER BY source_key
                """
            ).fetchall()
            entries = [
                SourceHealthEntry(
                    source_id=row["source_key"],
                    status=SourceHealthStatus.UNKNOWN,
                    last_attempt_at=row["last_attempt"],
                    health_reason=f"accepted={row['accepted']} failed={row['failed']} (native collector_runs substrate)",
                )
                for row in source_rows
            ]
            failed_total = sum(1 for row in source_rows if row["failed"])
            overall = (
                OperationalState.UNKNOWN
                if not source_rows
                else (OperationalState.DEGRADED if failed_total else OperationalState.HEALTHY)
            )
            last = self.last_run()
            return HealthPayload(
                clank_id=CLANK_ID,
                overall_status=overall,
                sources=entries,
                last_attempt_at=last.get("started_at") if last else None,
            )
        finally:
            con.close()

    # -- last run -----------------------------------------------------------

    def last_run(self) -> dict[str, Any] | None:
        con = open_readonly(self.db_path)
        if con is None:
            return None
        try:
            if not table_exists(con, "collector_runs"):
                return None
            row = con.execute(
                """
                SELECT run_id, source_key, collector_key, started_at, finished_at,
                       status, fixture_scenario, error
                FROM collector_runs ORDER BY started_at DESC, rowid DESC LIMIT 1
                """
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            result.pop("no_col", None)
            # execution_result is attested from the native run row's own
            # status column (per application-execution clock).
            result["execution_result"] = (
                "APPLICATION_SUCCESS" if row["status"] == "accepted" else "APPLICATION_FAILED"
            )
            return result
        finally:
            con.close()

    # -- run history --------------------------------------------------------

    def recent_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        con = open_readonly(self.db_path)
        if con is None:
            return []
        try:
            if not table_exists(con, "collector_runs"):
                return []
            rows = con.execute(
                """
                SELECT run_id, source_key, collector_key, started_at, finished_at, status, error
                FROM collector_runs ORDER BY started_at DESC, rowid DESC LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            con.close()
