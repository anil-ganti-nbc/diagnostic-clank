"""Smartwatch Clank read-only Fleet adapter - TRUTHFUL OPERATIONAL STAGE.

Live schema observed directly against the restored production DB
(smartwatch-clank.sqlite3, backed up via `real-state/`) on 2026-08-24.
Every table/column name below was read from that database; nothing is
invented. Tables observed but not consumed by this adapter (discoveries,
evidence_records, evidence_timeline, feedback, prelaunch_candidates,
soak_state, samsung_reconciliation_*, soak_host_migrations,
source_onboarding) carry no run/health-relevant semantics this adapter
needs and are left for a future pass rather than guessed at.

Observed schema (authoritative — do not extend without re-observing):

    runs(id, collector, started_at, finished_at, healthy, observation_count,
         warning, error, metadata_json, discovery_count, run_uuid,
         app_version, schema_version_at_run, config_fingerprint,
         git_revision)
    collector_health(collector, healthy, observed_count, previous_count,
                      warning, error, checked_at)
    schema_version(id, version, updated_at)
    observations(id, run_id, collector, identity, observed_at, source_url,
                 data_json)

`healthy` is a plain 0/1 boolean in both `runs` and `collector_health` -
there is no DEGRADED/BLOCKED_ZERO/ZERO_ITEMS distinction in this schema,
so the health mapping is deliberately two-valued (OK/FAILED); inventing a
finer vocabulary the DB does not express would violate the same
no-guessing rule this adapter existed to enforce at the introspection
stage. `runs.id` correlates with `finished_at` order in observed data but
is not a documented monotonic guarantee, so ordering uses `finished_at`.
No baseline/run-kind or epoch column exists anywhere in this schema;
those capabilities stay UNSUPPORTED, not invented.
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
from clank_runtime.contracts.enums import OperationalState, ReleaseChannel, SourceHealthStatus
from clank_runtime.contracts.health import HealthPayload, SourceHealthEntry
from clank_runtime.version import ADAPTER_CONTRACT_VERSION

CLANK_ID = "smartwatch-clank"

LIVE_SCHEMA_VALIDATION = "MAPPED"
LIVE_SCHEMA_VALIDATION_REASON = (
    "runs/collector_health/schema_version observed directly against the "
    "restored production DB on 2026-08-24; see module docstring")


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        return None


def _map_healthy(healthy: int | None) -> SourceHealthStatus:
    """Schema has only a 0/1 `healthy` column - two-valued by design,
    never upgraded to a finer vocabulary the DB doesn't express."""
    if healthy is None:
        return SourceHealthStatus.UNKNOWN
    return SourceHealthStatus.OK if healthy else SourceHealthStatus.FAILED


class SmartwatchClankAdapter:
    def __init__(
        self,
        *,
        db_path: Path | str,
        clank_version: str = "0.0.0",
        release_channel: str = "staging",
    ) -> None:
        self.db_path = Path(db_path)
        self.clank_version = clank_version
        self.release_channel = release_channel

    # -- identity ---------------------------------------------------------

    def identity(self) -> AdapterDescriptor:
        try:
            channel = ReleaseChannel(self.release_channel)
        except ValueError:
            channel = ReleaseChannel.STAGING
        return AdapterDescriptor(
            contract_version=ADAPTER_CONTRACT_VERSION,
            clank_id=CLANK_ID,
            clank_version=self.clank_version,
            release_channel=channel,
            capabilities=self.capabilities(),
            display_name="Smartwatch Clank",
            description="Connected-wearable collector; observer coverage at "
                        "truthful operational stage (schema live-mapped)",
        )

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_identity=True,
            supports_status=True,
            supports_health=True,
            supports_last_run=True,
            supports_telemetry=True,
            supports_delivery_accounting=False,  # no outbox/delivery table observed
            supports_version=True,
            supports_manual_run=False,
            supports_local_fallback=False,
        )

    # -- status / health ----------------------------------------------------

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
        last = self.last_run()
        last_at = _parse_dt(last.get("finished_at")) if last.get("supported") else None
        health = self.health()
        state = health.overall_status
        return AdapterStatus(
            clank_id=CLANK_ID,
            operational_state=state,
            release_channel=self.identity().release_channel,
            last_run_at=last_at,
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
        sources: list[SourceHealthEntry] = []
        warnings: list[str] = []
        try:
            if table_exists(con, "collector_health"):
                rows = fetchall(
                    con,
                    "SELECT collector, healthy, observed_count, warning, error, "
                    "checked_at FROM collector_health ORDER BY collector")
                for row in rows:
                    mapped = _map_healthy(row["healthy"])
                    sources.append(SourceHealthEntry(
                        source_id=row["collector"],
                        status=mapped,
                        last_attempt_at=_parse_dt(row["checked_at"]),
                        last_success_at=_parse_dt(row["checked_at"])
                        if mapped == SourceHealthStatus.OK else None,
                        observed_count=row["observed_count"],
                        health_reason=row["error"] or row["warning"],
                    ))
            else:
                warnings.append("collector_health table absent")
        except sqlite3.Error as exc:
            warnings.append(f"source health query issue: {exc}")
        finally:
            con.close()

        failed = sum(1 for s in sources if s.status == SourceHealthStatus.FAILED)
        overall = OperationalState.HEALTHY
        if not sources:
            overall = OperationalState.WARNING
            warnings.append("no collector_health rows recorded")
        elif failed == len(sources):
            overall = OperationalState.FAILED
        elif failed:
            overall = OperationalState.DEGRADED

        last_success = None
        for s in sources:
            if s.last_success_at and (last_success is None or s.last_success_at > last_success):
                last_success = s.last_success_at

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
        """Most recent run by `finished_at` (not `id` - not a documented
        monotonic guarantee, only an observed correlation)."""
        con = open_readonly(self.db_path)
        if con is None:
            return {"supported": False, "reason": "database missing",
                    "finished_at": None, "status": None, "run_kind": None}
        try:
            if not table_exists(con, "runs"):
                return {"supported": False, "reason": "runs table absent",
                        "finished_at": None, "status": None, "run_kind": None}
            row = con.execute(
                "SELECT id, collector, started_at, finished_at, healthy, "
                "observation_count, warning, error FROM runs "
                "ORDER BY finished_at DESC LIMIT 1").fetchone()
            if not row:
                return {"supported": True, "reason": "no rows",
                        "finished_at": None, "status": None, "run_kind": None}
            return {
                "supported": True,
                "run_id": str(row["id"]),
                "collector": row["collector"],
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
                "status": ("ok" if row["healthy"] else "failed"),
                # no baseline/run-kind column exists in this schema
                "run_kind": None,
                "observation_count": row["observation_count"],
                "warning": row["warning"],
                "error": row["error"],
            }
        except sqlite3.Error as exc:
            return {"supported": False, "reason": str(exc),
                    "finished_at": None, "status": None, "run_kind": None}
        finally:
            con.close()

    def schema_revision(self) -> int | str | None:
        con = open_readonly(self.db_path)
        if con is None:
            return None
        try:
            if not table_exists(con, "schema_version"):
                return None
            row = con.execute("SELECT MAX(version) FROM schema_version").fetchone()
            return row[0] if row else None
        except sqlite3.Error:
            return None
        finally:
            con.close()

    # -- introspection inventory (kept for parity with other adapters) ----

    def store_inventory(self) -> dict[str, Any]:
        con = open_readonly(self.db_path)
        if con is None:
            return {"available": False, "tables": {}}
        try:
            names = [r[0] for r in fetchall(
                con,
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            tables: dict[str, Any] = {}
            for name in names:
                try:
                    count = con.execute(
                        f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                except sqlite3.Error:
                    count = None
                tables[name] = count
            return {
                "available": True,
                "live_schema_validation": LIVE_SCHEMA_VALIDATION,
                "reason": LIVE_SCHEMA_VALIDATION_REASON,
                "tables": tables,
            }
        except sqlite3.Error:
            return {"available": False, "tables": {}}
        finally:
            con.close()
