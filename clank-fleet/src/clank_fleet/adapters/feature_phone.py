"""Feature Phone Clank read-only Fleet adapter.

Preserves Feature Phone's own health/absence semantics; Unified only
translates declared run status into the Fleet envelope.
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
    OperationalState,
    ReleaseChannel,
    RunKind,
    SourceHealthStatus,
)
from clank_runtime.contracts.health import HealthPayload, SourceHealthEntry
from clank_runtime.contracts.telemetry import TelemetryEnvelope
from clank_runtime.version import ADAPTER_CONTRACT_VERSION

log = logging.getLogger("clank_fleet.adapters.feature_phone")

CLANK_ID = "feature-phone-clank"


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


def _map_run_status(status: str | None) -> SourceHealthStatus:
    """Shared vocabulary across adapters (M1.5).

    Maps each fleet's native run-status words onto the shared health enum.
    Unmapped values stay UNKNOWN — mapping may never upgrade ambiguous or
    unrecognized evidence to OK.

    Fleet vocabularies covered:
    - feature-phone : ok / failed / error / blocked_zero_result
    - smartphone    : success / degraded (+ ok legacy)
    - watch         : SUCCESS / PARTIAL / FAILURE-class strings (case-insensitive)
    """
    raw = (status or "unknown").lower()
    return {
        # canonical + feature-phone
        "ok": SourceHealthStatus.OK,
        "failed": SourceHealthStatus.FAILED,
        "error": SourceHealthStatus.FAILED,
        "blocked_zero_result": SourceHealthStatus.BLOCKED_ZERO,
        "degraded": SourceHealthStatus.DEGRADED,
        # smartphone-clank native vocabulary
        "success": SourceHealthStatus.OK,
        # watch-clank native vocabulary (source_component_states)
        "partial": SourceHealthStatus.DEGRADED,
        "zero_items": SourceHealthStatus.ZERO_ITEMS,
        "blocked": SourceHealthStatus.BLOCKED_ZERO,
    }.get(raw, SourceHealthStatus.UNKNOWN)


class FeaturePhoneAdapter:
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

    def capability_states(self) -> dict[str, dict[str, str]]:
        return {
            "collection": {"state": "active",
                           "evidence": "HMD listings/sitemap observations, "
                                       "append-only"},
            "health": {"state": "active",
                       "evidence": "blocked_zero_result + collector run "
                                   "metrics"},
            "events": {"state": "active",
                       "evidence": "deterministic change-event diffing"},
            "delivery": {"state": "supported_undeployed",
                         "evidence": "durable outbox exists in code but was "
                                     "absent from the deployed revision at "
                                     "snapshot time (v0.2 §3 specimen)"},
            "qc": {"state": "unknown_or_unverified",
                   "evidence": "no review substrate observed in mapped "
                               "schema subset"},
            "scheduler_trace": {"state": "supported_unconfigured",
                                "evidence": "prod cron; P-4 trace plane when "
                                            "probe records exist"},
            "continuity": {"state": "active",
                           "evidence": "fpc-epoch-2 hard boundary carried by "
                                       "continuity registry"},
            "survivability": {"state": "active",
                              "evidence": "ACT-011 epoch-2 recovery point: "
                                          "restore-verified; durable off-host "
                                          "still unproven"},
        }

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
            display_name="Feature Phone Clank",
            description="HMD/Nokia feature-phone catalogue change detection",
        )

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_identity=True,
            supports_status=True,
            supports_health=True,
            supports_last_run=True,
            supports_telemetry=True,
            supports_delivery_accounting=False,  # no outbox in Stage 1A FP
            supports_version=True,
            supports_manual_run=False,
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
        last = self.last_run()
        last_at = _parse_dt(last.get("finished_at") or last.get("started_at")) if last else None
        last_ok = None
        con = open_readonly(self.db_path)
        if con is not None:
            try:
                if table_exists(con, "collector_runs"):
                    row = con.execute(
                        "SELECT finished_at FROM collector_runs WHERE status='ok' "
                        "ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                    if row:
                        last_ok = _parse_dt(row[0])
            finally:
                con.close()
        state = OperationalState.HEALTHY if last_ok else OperationalState.WARNING
        if last and _map_run_status(last.get("status")) in {
            SourceHealthStatus.FAILED,
            SourceHealthStatus.BLOCKED_ZERO,
        }:
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
        if not self.db_path.exists():
            return HealthPayload(
                clank_id=CLANK_ID,
                overall_status=OperationalState.UNKNOWN,
                warnings=[f"database missing: {self.db_path}"],
                is_stale_cache=True,
                observed_at=now,
            )
        sources: list[SourceHealthEntry] = []
        warnings: list[str] = []
        con = open_readonly(self.db_path)
        assert con is not None
        try:
            if table_exists(con, "collector_runs"):
                rows = fetchall(
                    con,
                    """
                    SELECT source_key, status, finished_at, discovered
                    FROM collector_runs
                    WHERE id IN (SELECT MAX(id) FROM collector_runs GROUP BY source_key)
                    ORDER BY source_key
                    """,
                )
                for row in rows:
                    mapped = _map_run_status(row["status"])
                    sources.append(
                        SourceHealthEntry(
                            source_id=row["source_key"],
                            status=mapped,
                            last_attempt_at=_parse_dt(row["finished_at"]),
                            last_success_at=_parse_dt(row["finished_at"])
                            if mapped == SourceHealthStatus.OK
                            else None,
                            observed_count=row["discovered"]
                            if "discovered" in row.keys()
                            else None,
                            health_reason=row["status"],
                        )
                    )
            else:
                warnings.append("collector_runs table absent")
        except sqlite3.Error as exc:
            # Column may differ across schema versions
            warnings.append(f"source health query issue: {exc}")
            try:
                rows = fetchall(
                    con,
                    """
                    SELECT source_key, status, finished_at
                    FROM collector_runs
                    WHERE id IN (SELECT MAX(id) FROM collector_runs GROUP BY source_key)
                    ORDER BY source_key
                    """,
                )
                for row in rows:
                    mapped = _map_run_status(row["status"])
                    sources.append(
                        SourceHealthEntry(
                            source_id=row["source_key"],
                            status=mapped,
                            last_attempt_at=_parse_dt(row["finished_at"]),
                            health_reason=row["status"],
                        )
                    )
            except sqlite3.Error as exc2:
                warnings.append(str(exc2))
        finally:
            con.close()

        failed = sum(
            1
            for s in sources
            if s.status in {SourceHealthStatus.FAILED, SourceHealthStatus.BLOCKED_ZERO}
        )
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
            warnings=warnings,
            is_stale_cache=False,
            observed_at=now,
        )

    def last_run(self) -> dict[str, Any] | None:
        con = open_readonly(self.db_path)
        if con is None:
            return None
        try:
            if not table_exists(con, "collector_runs"):
                return None
            row = con.execute(
                "SELECT id, source_key, status, started_at, finished_at FROM collector_runs "
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
            if not table_exists(con, "collector_runs"):
                return []
            # Prefer richer columns when present
            cols = {r[1] for r in con.execute("PRAGMA table_info(collector_runs)").fetchall()}
            select_cols = ["id", "source_key", "status", "started_at", "finished_at"]
            for optional in ("discovered", "events_created"):
                if optional in cols:
                    select_cols.append(optional)
            sql = (
                f"SELECT {', '.join(select_cols)} FROM collector_runs "
                "ORDER BY id DESC LIMIT ?"
            )
            rows = fetchall(con, sql, (limit,))
            for row in rows:
                keys = row.keys()
                observed = row["discovered"] if "discovered" in keys else None
                events = row["events_created"] if "events_created" in keys else None
                out.append(
                    TelemetryEnvelope(
                        clank_id=CLANK_ID,
                        run_id=str(row["id"]),
                        source_id=row["source_key"],
                        started_at=_parse_dt(row["started_at"]),
                        finished_at=_parse_dt(row["finished_at"]),
                        run_kind=RunKind.NORMAL_RUN,
                        source_status=_map_run_status(row["status"]),
                        observed_count=observed,
                        event_count=events,
                        # delivery not tracked — leave null, not zero
                        delivery_count=None,
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
                "lifecycle": "production",
                "health": s.status.value,
                "last_success_at": s.last_success_at.isoformat() if s.last_success_at else None,
                "observed_count": s.observed_count,
                "warnings": s.warnings,
            }
            for s in health.sources
        ]
