"""Tablet Clank read-only Fleet adapter (P-4.6 onboarding).

Tablet is intentionally RETIRED: finite soak completed; Promotion Wave 1
moved Honor/TCL to a manual/on-demand production allowlist; no scheduler
is active by design. The obsolete ``tablet-clank-soak.service`` unit file
proves nothing - the application refuses retired configuration.

Native semantics preserved from canonical participant source:
- ``collector_runs``: NATIVE per-attempt run table written for every
  collector execution regardless of findings.
- ``sources`` / ``source_state``: declared sources with baseline tracking.
- ``change_events``: change detection substrate.
- ``schema_migrations``: version-stamped migrations.
- No delivery substrate -> unsupported_by_policy.
- No QC substrate -> unsupported.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from clank_fleet.adapters.base import fetchall, open_readonly, table_exists
from clank_runtime.contracts.adapter import (
    AdapterCapabilities,
    AdapterDescriptor,
    AdapterStatus,
)
from clank_runtime.contracts.enums import OperationalState, ReleaseChannel, \
    SourceHealthStatus
from clank_runtime.contracts.health import HealthPayload, SourceHealthEntry
from clank_runtime.version import ADAPTER_CONTRACT_VERSION

CLANK_ID = "tablet-clank"


def _parse_dt(value):
    if value is None:
        return None
    try:
        from datetime import datetime as dt
        d = dt.fromisoformat(str(value).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=UTC)
    except ValueError:
        return None


class TabletClankAdapter:
    def __init__(self, *, db_path: Path | str,
                 clank_version: str = "0.0.1",
                 release_channel: str = "deprecated"):
        self.db_path = Path(db_path)
        self.clank_version = clank_version
        self.release_channel = release_channel

    def identity(self) -> AdapterDescriptor:
        try:
            channel = ReleaseChannel(self.release_channel)
        except ValueError:
            channel = ReleaseChannel.DEPRECATED
        return AdapterDescriptor(
            contract_version=ADAPTER_CONTRACT_VERSION,
            clank_id=CLANK_ID,
            clank_version=self.clank_version,
            release_channel=channel,
            capabilities=self.capabilities(),
            display_name="Tablet Clank",
            description="First-party tablet catalogue changes; retired "
                        "soak lane with manual/on-demand production "
                        "allowlist",
        )

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_identity=True,
            supports_status=True,
            supports_health=True,
            supports_last_run=True,
            supports_telemetry=False,
            supports_delivery_accounting=False,
            supports_version=True,
            supports_manual_run=True,
            supports_local_fallback=False,
        )

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
        health = self.health()
        return AdapterStatus(
            clank_id=CLANK_ID,
            operational_state=health.overall_status,
            release_channel=self.identity().release_channel,
            last_run_at=health.last_attempt_at,
            last_success_at=health.last_success_at,
            version=self.clank_version,
            location="local",
            observed_at=now,
        )

    def health(self) -> HealthPayload:
        now = datetime.now(UTC)
        if not self.db_path.exists():
            return HealthPayload(
                clank_id=CLANK_ID,
                overall_status=OperationalState.UNKNOWN,
                warnings=[f"database missing: {self.db_path}"],
                is_stale_cache=True,
                observed_at=now,
            )
        con = open_readonly(self.db_path)
        assert con is not None
        sources = []
        warnings = []
        try:
            if table_exists(con, "collector_runs"):
                rows = fetchall(
                    con,
                    "SELECT c.source_id, c.status, c.raw_count,"
                    " c.accepted_count, c.error, c.started_at,"
                    " c.finished_at FROM collector_runs c"
                    " WHERE c.id = (SELECT MAX(c2.id) FROM collector_runs c2"
                    " WHERE c2.source_id = c.source_id)"
                    " ORDER BY c.source_id")
                for row in rows:
                    raw_status = (row["status"] or "unknown").lower()
                    mapped = {"ok": SourceHealthStatus.OK,
                              "completed": SourceHealthStatus.OK,
                              }.get(raw_status, SourceHealthStatus.FAILED
                                    if "fail" in raw_status or
                                       "error" in raw_status
                                    else SourceHealthStatus.UNKNOWN)
                    sources.append(SourceHealthEntry(
                        source_id=row["source_id"],
                        status=mapped,
                        last_attempt_at=_parse_dt(row["started_at"]),
                        last_success_at=_parse_dt(row["finished_at"])
                        if mapped == SourceHealthStatus.OK else None,
                        observed_count=row["accepted_count"],
                        health_reason=row["error"],
                    ))
            else:
                warnings.append("collector_runs table absent")
        except sqlite3.Error as exc:
            warnings.append(f"query issue: {exc}")
        finally:
            con.close()

        failed = sum(1 for s in sources if s.status == SourceHealthStatus.FAILED)
        overall = OperationalState.HEALTHY
        if not sources:
            overall = OperationalState.UNKNOWN
            warnings.append("no collector_runs rows recorded")
        elif failed == len(sources):
            overall = OperationalState.FAILED
        elif failed:
            overall = OperationalState.DEGRADED

        last_success = max((s.last_success_at for s in sources
                            if s.last_success_at), default=None)
        return HealthPayload(
            clank_id=CLANK_ID,
            overall_status=overall,
            sources=sources,
            last_success_at=last_success,
            warnings=warnings,
            is_stale_cache=False,
            observed_at=now,
        )

    def last_run(self) -> dict[str, Any]:
        """Latest native collector_run. Clock: native_run_row."""
        con = open_readonly(self.db_path)
        if con is None:
            return {"supported": False, "reason": "database missing",
                    "finished_at": None, "status": None, "run_kind": None}
        try:
            if not table_exists(con, "collector_runs"):
                return {"supported": False,
                        "reason": "collector_runs table absent",
                        "finished_at": None, "status": None,
                        "run_kind": None}
            row = con.execute(
                "SELECT id, source_id, started_at, finished_at, status,"
                " accepted_count, new_count FROM collector_runs "
                "ORDER BY COALESCE(finished_at, started_at) DESC LIMIT 1"
            ).fetchone()
            if not row:
                return {"supported": True, "reason": "no rows",
                        "finished_at": None, "status": None,
                        "run_kind": None}
            return {
                "supported": True,
                "run_id": str(row["id"]),
                "source_id": row["source_id"],
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
                "status": ("ok" if row["status"] in ("ok", "completed")
                           else "failed"),
                "clock": "native_run_row",
                "accepted_count": row["accepted_count"],
                "new_count": row["new_count"],
                "run_kind": None,
            }
        except sqlite3.Error as exc:
            return {"supported": False, "reason": str(exc),
                    "finished_at": None, "status": None, "run_kind": None}
        finally:
            con.close()

    def generation_summary(self) -> dict[str, Any]:
        con = open_readonly(self.db_path)
        if con is None:
            return {"available": False}
        try:
            out = {"available": True}
            for t in ("products", "observations", "change_events"):
                out[t] = (con.execute(
                    f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    if table_exists(con, t) else None)
            return out
        finally:
            con.close()

    def schema_revision(self) -> int | None:
        con = open_readonly(self.db_path)
        if con is None or not table_exists(con, "schema_migrations"):
            return None
        try:
            row = con.execute(
                "SELECT MAX(version) FROM schema_migrations").fetchone()
            return row[0] if row else None
        except sqlite3.Error:
            return None
        finally:
            con.close()

    def capability_states(self) -> dict[str, dict[str, str]]:
        db_present = self.db_path.exists()
        return {
            "collection": {
                "state": "active" if db_present else "unknown_or_unverified",
                "evidence": f"store {'present' if db_present else 'absent'}:"
                            f" {self.db_path}",
            },
            "health": {
                "state": "active",
                "evidence": "collector_runs latest attempt per source_id",
            },
            "events": {
                "state": "unknown_or_unverified",
                "evidence": "change_events table exists in schema but no "
                            "live event activity observed",
            },
            "delivery": {
                "state": "unsupported_by_policy",
                "evidence": "no notification/delivery substrate designed",
            },
            "qc": {
                "state": "unsupported",
                "evidence": "no review/QC substrate in mapped schema",
            },
            "scheduler_trace": {
                "state": "unsupported_by_policy",
                "evidence": "RETIRED: no active scheduler by design; "
                            "finite soak completed; Promotion Wave 1 moved "
                            "Honor/TCL to manual/on-demand production",
            },
            "continuity": {
                "state": "unknown_or_unverified",
                "evidence": "no destructive incident recorded; continuity "
                            "unproven and unassumed",
            },
            "survivability": {
                "state": "unknown_or_unverified",
                "evidence": "no backup evidence records registered for "
                            "this lane",
            },
            "baseline_run_kind": {
                "state": "unsupported_by_policy",
                "evidence": "baseline tracked via source_state.baseline_"
                            "complete but no dedicated baseline/run-kind "
                            "column in collector_runs",
            },
        }
