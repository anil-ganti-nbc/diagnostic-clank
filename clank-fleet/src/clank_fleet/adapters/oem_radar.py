"""OEM Radar read-only Fleet adapter.

Translates OEM Radar SQLite + config surfaces into Unified contracts.
Never writes, never runs collectors, never touches Discord.
"""

from __future__ import annotations

import logging
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
from clank_runtime.contracts.enums import (
    DeliveryStatus,
    OperationalState,
    ReleaseChannel,
    RunKind,
    SourceHealthStatus,
)
from clank_runtime.contracts.health import HealthPayload, SourceHealthEntry
from clank_runtime.contracts.telemetry import TelemetryEnvelope, TelemetryEventRecord
from clank_runtime.version import ADAPTER_CONTRACT_VERSION

log = logging.getLogger("clank_fleet.adapters.oem_radar")

CLANK_ID = "oem-radar"


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


class OemRadarAdapter:
    def __init__(
        self,
        *,
        db_path: Path | str,
        clank_version: str = "0.0.1",
        release_channel: str = "experimental",
    ) -> None:
        self.db_path = Path(db_path)
        self.clank_version = clank_version
        self.release_channel = release_channel

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
            display_name="OEM Radar",
            description="Boutique PC OEM product-change intelligence",
        )

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_identity=True,
            supports_status=True,
            supports_health=True,
            supports_last_run=True,
            supports_telemetry=True,
            supports_delivery_accounting=True,  # outbox table when present
            supports_version=True,
            supports_manual_run=False,
            supports_pause=False,
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
        last_run = self.last_run()
        last_at = _parse_dt(last_run.get("started_at") if last_run else None)
        last_ok = None
        con = open_readonly(self.db_path)
        if con is not None:
            try:
                if table_exists(con, "crawler_runs"):
                    row = con.execute(
                        "SELECT finished_at FROM crawler_runs WHERE status='ok' "
                        "ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                    if row:
                        last_ok = _parse_dt(row[0])
            finally:
                con.close()
        state = OperationalState.HEALTHY if last_ok else OperationalState.WARNING
        if last_run and last_run.get("status") not in (None, "ok"):
            state = OperationalState.DEGRADED
        return AdapterStatus(
            clank_id=CLANK_ID,
            operational_state=state,
            release_channel=self.identity().release_channel,
            last_run_at=last_at,
            last_success_at=last_ok,
            version=self.clank_version,
            location="local",
            observed_at=now,
        )

    def health(self) -> HealthPayload:
        now = datetime.now(UTC)
        sources: list[SourceHealthEntry] = []
        warnings: list[str] = []
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
        try:
            if table_exists(con, "crawler_runs"):
                rows = fetchall(
                    con,
                    """
                    SELECT source_key, status, finished_at, stats_json
                    FROM crawler_runs
                    WHERE id IN (
                        SELECT MAX(id) FROM crawler_runs GROUP BY source_key
                    )
                    ORDER BY source_key
                    """,
                )
                for row in rows:
                    status_raw = (row["status"] or "unknown").lower()
                    mapped = {
                        "ok": SourceHealthStatus.OK,
                        "failed": SourceHealthStatus.FAILED,
                        "degraded": SourceHealthStatus.DEGRADED,
                        "error": SourceHealthStatus.FAILED,
                    }.get(status_raw, SourceHealthStatus.UNKNOWN)
                    # OEM Radar encodes unexpected zero in run status/errors, not as healthy zero.
                    sources.append(
                        SourceHealthEntry(
                            source_id=row["source_key"],
                            status=mapped,
                            last_attempt_at=_parse_dt(row["finished_at"]),
                            last_success_at=_parse_dt(row["finished_at"])
                            if status_raw == "ok"
                            else None,
                        )
                    )
            else:
                warnings.append("crawler_runs table absent")
        finally:
            con.close()

        failed = sum(1 for s in sources if s.status == SourceHealthStatus.FAILED)
        overall = OperationalState.HEALTHY
        if not sources:
            overall = OperationalState.WARNING
            warnings.append("no source runs recorded")
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
            last_attempt_at=now,
            warnings=warnings,
            is_stale_cache=False,
            observed_at=now,
        )

    def eligible_count(self) -> dict[str, Any]:
        """M4.5 coverage: change events a human could review (alert_reviews)."""
        con = open_readonly(self.db_path)
        if con is None:
            return {"eligible_total": None}
        try:
            table = "change_events" if table_exists(con, "change_events") else None
            total = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] \
                if table else None
            reviewed = (con.execute("SELECT COUNT(*) FROM alert_reviews").fetchone()[0]
                        if table_exists(con, "alert_reviews") else None)
            return {"eligible_total": total, "reviewed_total": reviewed}
        except sqlite3.Error:
            return {"eligible_total": None}
        finally:
            con.close()

    def last_run(self) -> dict[str, Any] | None:
        con = open_readonly(self.db_path)
        if con is None:
            return None
        try:
            if not table_exists(con, "crawler_runs"):
                return None
            row = con.execute(
                "SELECT id, source_key, status, started_at, finished_at FROM crawler_runs "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if not row:
                return None
            return {
                "run_id": str(row["id"]),
                "source_id": row["source_key"],
                "status": row["status"],
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
            }
        finally:
            con.close()

    def telemetry(self, *, limit: int = 20) -> list[TelemetryEnvelope]:
        con = open_readonly(self.db_path)
        if con is None:
            return []
        out: list[TelemetryEnvelope] = []
        try:
            if not table_exists(con, "crawler_runs"):
                return []
            rows = fetchall(
                con,
                "SELECT id, source_key, status, started_at, finished_at, stats_json "
                "FROM crawler_runs ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            delivery_pending = 0
            if table_exists(con, "notification_outbox"):
                try:
                    delivery_pending = con.execute(
                        "SELECT COUNT(*) FROM notification_outbox WHERE status='pending'"
                    ).fetchone()[0]
                except sqlite3.Error:
                    delivery_pending = 0
            for row in rows:
                status_raw = (row["status"] or "unknown").lower()
                mapped = {
                    "ok": SourceHealthStatus.OK,
                    "failed": SourceHealthStatus.FAILED,
                    "degraded": SourceHealthStatus.DEGRADED,
                }.get(status_raw, SourceHealthStatus.UNKNOWN)
                out.append(
                    TelemetryEnvelope(
                        clank_id=CLANK_ID,
                        run_id=str(row["id"]),
                        source_id=row["source_key"],
                        started_at=_parse_dt(row["started_at"]),
                        finished_at=_parse_dt(row["finished_at"]),
                        run_kind=RunKind.NORMAL_RUN,
                        source_status=mapped,
                        delivery_count=None if delivery_pending is None else None,
                        extensions={
                            "delivery_pending_total": delivery_pending,
                            "stats_json_present": bool(row["stats_json"]),
                        },
                    )
                )
        finally:
            con.close()
        return out

    def source_summary(self) -> list[dict[str, Any]]:
        health = self.health()
        return [
            {
                "source_id": s.source_id,
                "lifecycle": "production",  # OEM config distinguishes; default production for enabled runs
                "health": s.status.value,
                "last_success_at": s.last_success_at.isoformat() if s.last_success_at else None,
                "observed_count": s.observed_count,
                "warnings": s.warnings,
            }
            for s in health.sources
        ]

    def capability_states(self) -> dict[str, dict[str, str]]:
        """v0.2 evidence-bearing capability states (never bare booleans)."""
        db_present = self.db_path.exists()
        con = open_readonly(self.db_path) if db_present else None
        outbox = False
        change_events = False
        reviews = False
        if con is not None:
            try:
                outbox = table_exists(con, "notification_outbox")
                change_events = table_exists(con, "change_events")
                reviews = table_exists(con, "alert_reviews")
            finally:
                con.close()
        return {
            "collection": {
                "state": "active" if db_present else "unknown_or_unverified",
                "evidence": f"crawler_runs substrate, store "
                            f"{'present' if db_present else 'absent'}",
            },
            "health": {
                "state": "active",
                "evidence": "latest crawler run per source_key; unexpected "
                            "zero encoded in status/errors, never healthy-zero",
            },
            "events": {
                "state": "active" if change_events else "unknown_or_unverified",
                "evidence": "change_events table "
                            + ("present" if change_events else "not observed"),
            },
            "delivery": {
                "state": "supported_unconfigured" if outbox
                         else "unknown_or_unverified",
                "evidence": "notification_outbox "
                            + ("present: generation vs delivery tracked "
                               "separately" if outbox else "not observed"),
            },
            "qc": {
                "state": "active" if reviews else "unknown_or_unverified",
                "evidence": "alert_reviews table "
                            + ("present" if reviews else "not observed"),
            },
            "scheduler_trace": {
                "state": "supported_unconfigured",
                "evidence": "P-4 trace plane consumes probe records when present",
            },
            "continuity": {
                "state": "active",
                "evidence": "no destructive incident recorded for this lane; "
                            "CONTIGUOUS unless registry says otherwise",
            },
            "survivability": {
                "state": "unknown_or_unverified",
                "evidence": "no backup evidence records registered for this lane",
            },
        }
