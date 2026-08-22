"""Smartphone Clank read-only Fleet adapter.

Phase 2C onboarding. Read-only introspection of the soak DB: per-collector run
metrics (the real health substrate — the `source_health` table is dead schema),
timeline event taxonomy, delivery ledger, and confidence/QC surfaces. Fields
the deployed revision does not evidence stay UNKNOWN/null.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from clank_fleet.adapters.base import fetchall, open_readonly, table_exists
from clank_fleet.adapters.feature_phone import _map_run_status, _parse_dt
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

CLANK_ID = "smartphone-clank"


class SmartphoneClankAdapter:
    def __init__(
        self,
        *,
        db_path: Path | str,
        clank_version: str = "0.0.1",
        release_channel: str = "production",
    ) -> None:
        self.db_path = Path(db_path)
        self.clank_version = clank_version
        self.release_channel = release_channel

    def identity(self) -> AdapterDescriptor:
        try:
            channel = ReleaseChannel(self.release_channel)
        except ValueError:
            channel = ReleaseChannel.PRODUCTION
        return AdapterDescriptor(
            contract_version=ADAPTER_CONTRACT_VERSION,
            clank_id=CLANK_ID,
            clank_version=self.clank_version,
            release_channel=channel,
            capabilities=self.capabilities(),
            display_name="Smartphone Clank",
            description="Samsung + wave-1 OEM smartphone catalogue change detection",
        )

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_identity=True,
            supports_status=True,
            supports_health=True,
            supports_last_run=True,
            supports_telemetry=True,
            supports_delivery_accounting=True,  # webhook_deliveries persisted per alert decision
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
        last_at = _parse_dt(last.get("started_at")) if last else None
        return AdapterStatus(
            clank_id=CLANK_ID,
            operational_state=OperationalState.HEALTHY if last_at else OperationalState.UNKNOWN,
            message="last collector metric row present" if last_at else "no runs recorded",
            is_stale=last_at is None,
            observed_at=now,
        )

    def schema_revision(self) -> str | None:
        con = open_readonly(self.db_path)
        if con is None or not table_exists(con, "alembic_version"):
            return None
        try:
            row = con.execute("SELECT version_num FROM alembic_version LIMIT 1").fetchone()
            return row["version_num"] if row else None
        finally:
            con.close()

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
            if table_exists(con, "collector_run_metrics"):
                rows = fetchall(
                    con,
                    """
                    SELECT m.collector_name, m.source_name, m.status, m.started_at, m.finished_at,
                           m.candidates_found, m.meaningful_changes
                    FROM collector_run_metrics m
                    WHERE m.finished_at = (
                        SELECT MAX(m2.finished_at) FROM collector_run_metrics m2
                        WHERE m2.collector_name = m.collector_name
                    )
                    ORDER BY m.collector_name
                    """,
                )
                for row in rows:
                    mapped = _map_run_status(row["status"])
                    ok = mapped == SourceHealthStatus.OK
                    sources.append(
                        SourceHealthEntry(
                            source_id=row["collector_name"],
                            status=mapped,
                            last_attempt_at=_parse_dt(row["started_at"]),
                            last_success_at=_parse_dt(row["finished_at"]) if ok else None,
                            observed_count=row["candidates_found"],
                            health_reason=row["status"],
                        )
                    )
            elif table_exists(con, "source_health"):
                warnings.append("only dead-schema source_health present; no metrics")
            else:
                warnings.append("no run-metrics tables present")
        except sqlite3.Error as exc:
            warnings.append(f"health query issue: {exc}")
        finally:
            con.close()

        failed = sum(1 for s in sources if s.status in {SourceHealthStatus.FAILED, SourceHealthStatus.BLOCKED_ZERO})
        overall = OperationalState.HEALTHY
        if not sources:
            overall = OperationalState.WARNING
            warnings.append("no collector metrics recorded")
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
        if con is None or not table_exists(con, "collector_run_metrics"):
            return None
        try:
            # M1.5: id is a UUID string — lexicographic order is meaningless and
            # once selected an Aug-18 row while the true latest ran today.
            # Order by the real run timestamp instead (NULLs sort last on DESC).
            row = con.execute(
                "SELECT id, collector_name AS source_id, status, started_at, finished_at, run_reason "
                "FROM collector_run_metrics ORDER BY finished_at DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None
        except sqlite3.Error:
            return None
        finally:
            con.close()

    def telemetry(self, *, limit: int = 20) -> list[TelemetryEnvelope]:
        con = open_readonly(self.db_path)
        if con is None or not table_exists(con, "collector_run_metrics"):
            return []
        out: list[TelemetryEnvelope] = []
        try:
            rows = fetchall(
                con,
                """
                SELECT id, collector_name, status, started_at, finished_at,
                       candidates_found, meaningful_changes, alerts_sent, run_reason
                FROM collector_run_metrics ORDER BY finished_at DESC, id DESC LIMIT ?
                """,
                (limit,),
            )
            for row in rows:
                reason = (row["run_reason"] or "").lower()
                kind = RunKind.BASELINE_BUILD if "baseline" in reason else RunKind.NORMAL_RUN
                out.append(
                    TelemetryEnvelope(
                        clank_id=CLANK_ID,
                        run_id=str(row["id"]),
                        source_id=row["collector_name"],
                        started_at=_parse_dt(row["started_at"]),
                        finished_at=_parse_dt(row["finished_at"]),
                        run_kind=kind,
                        source_status=_map_run_status(row["status"]),
                        observed_count=row["candidates_found"],
                        event_count=row["meaningful_changes"],
                        delivery_count=row["alerts_sent"],
                    )
                )
        finally:
            con.close()
        return out

    def delivery_summary(self) -> dict[str, Any]:
        """Generation vs delivery distinction: webhook_deliveries rows record every
        eligibility decision; `alerts` means actually delivered to Discord."""
        con = open_readonly(self.db_path)
        if con is None:
            return {}
        out: dict[str, Any] = {"delivery_rows_by_reason": {}, "delivered_alerts_total": None}
        try:
            if table_exists(con, "webhook_deliveries"):
                cols = [r[1] for r in con.execute("PRAGMA table_info(webhook_deliveries)")]
                reason_col = "reason" if "reason" in cols else ("event_reason" if "event_reason" in cols else None)
                if reason_col:
                    out["delivery_rows_by_reason"] = {
                        r[0]: r[1]
                        for r in con.execute(
                            f"SELECT {reason_col}, COUNT(*) FROM webhook_deliveries GROUP BY 1"
                        ).fetchall()
                    }
                attempted = con.execute("SELECT COUNT(*) FROM webhook_deliveries").fetchone()[0]
                out["delivery_attempts_total"] = attempted
            if table_exists(con, "alerts"):
                out["delivered_alerts_total"] = con.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
        except sqlite3.Error as exc:
            out["error"] = str(exc)
        finally:
            con.close()
        return out

    def qc_summary(self) -> dict[str, Any]:
        con = open_readonly(self.db_path)
        if con is None:
            return {}
        out: dict[str, Any] = {}
        try:
            if table_exists(con, "rejected_candidates"):
                out["rejected_candidates_total"] = con.execute(
                    "SELECT COUNT(*) FROM rejected_candidates"
                ).fetchone()[0]
            if table_exists(con, "confidence_ledger"):
                out["confidence_ledger_entries"] = con.execute(
                    "SELECT COUNT(*) FROM confidence_ledger"
                ).fetchone()[0]
            if table_exists(con, "analyst_actions"):
                out["analyst_action_counts"] = {
                    r[0]: r[1]
                    for r in con.execute(
                        "SELECT action_type, COUNT(*) FROM analyst_actions GROUP BY action_type"
                    ).fetchall()
                }
        except sqlite3.Error as exc:
            out["error"] = str(exc)
        finally:
            con.close()
        return out

    def eligible_count(self) -> dict[str, Any]:
        """M4.5 coverage: timeline events a human could disposition."""
        con = open_readonly(self.db_path)
        if con is None or not table_exists(con, "timeline_events"):
            return {"eligible_total": None}
        try:
            return {"eligible_total": con.execute(
                "SELECT COUNT(*) FROM timeline_events").fetchone()[0]}
        except sqlite3.Error:
            return {"eligible_total": None}
        finally:
            con.close()

    def qc_records(self, *, limit: int = 1000) -> list[dict[str, Any]]:
        """Row-level human analyst actions (M4). Machine-scored
        confidence_ledger entries are deliberately EXCLUDED: they are not
        human QC decisions."""
        con = open_readonly(self.db_path)
        if con is None or not table_exists(con, "analyst_actions"):
            return []
        out: list[dict[str, Any]] = []
        try:
            rows = fetchall(
                con,
                """
                SELECT id AS original_record_id, action AS raw_disposition,
                       target_type, target_id, actor_label, reason,
                       before_state, after_state, created_at AS observed_at
                FROM analyst_actions ORDER BY id LIMIT ?
                """,
                (limit,),
            )
            for row in rows:
                rec = dict(row)
                rec["source_table"] = "analyst_actions"
                rec["subject_type"] = rec.get("target_type") or "unknown"
                rec["subject_id"] = rec.pop("target_id", None)
                out.append(rec)
        except sqlite3.Error:
            return out
        finally:
            con.close()
        return out

    def timeline_taxonomy(self) -> dict[str, int] | None:
        con = open_readonly(self.db_path)
        if con is None or not table_exists(con, "timeline_events"):
            return None
        try:
            return {
                r[0]: r[1]
                for r in con.execute(
                    "SELECT event_type, COUNT(*) FROM timeline_events GROUP BY event_type ORDER BY 2 DESC"
                ).fetchall()
            }
        except sqlite3.Error:
            return None
        finally:
            con.close()
