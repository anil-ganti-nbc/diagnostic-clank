"""Watch Clank read-only Fleet adapter.

Control-specimen onboarding (Phase 2C approved order). Read-only SQLite
introspection of the operational epoch/event/QC state; preserves Watch's own
novelty and QC semantics. Delivery accounting is not persisted by Watch, so
those fields stay null/UNKNOWN rather than fabricated.
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

CLANK_ID = "watch-clank"


class WatchClankAdapter:
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

    # -- identity -----------------------------------------------------------

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
            display_name="Watch Clank",
            description="Four-brand watch launch/specialist intelligence (control specimen)",
        )

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_identity=True,
            supports_status=True,
            supports_health=True,
            supports_last_run=True,
            supports_telemetry=True,
            supports_delivery_accounting=False,  # Discord sends are fire-and-forget; not persisted
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
        last = self.last_run()
        last_at = _parse_dt(last.get("started_at")) if last else None
        return AdapterStatus(
            clank_id=CLANK_ID,
            operational_state=OperationalState.HEALTHY if last_at else OperationalState.UNKNOWN,
            message=f"last collector run {row_str(last, 'started_at')}" if last else "no runs recorded",
            is_stale=False if last_at else True,
            observed_at=now,
        )

    def schema_revision(self) -> str | None:
        con = open_readonly(self.db_path)
        if con is None:
            return None
        try:
            if not table_exists(con, "alembic_version"):
                return None
            row = con.execute("SELECT version_num FROM alembic_version LIMIT 1").fetchone()
            return row["version_num"] if row else None
        finally:
            con.close()

    def current_epoch(self) -> dict[str, Any] | None:
        con = open_readonly(self.db_path)
        if con is None or not table_exists(con, "operational_epochs"):
            return None
        try:
            row = con.execute(
                "SELECT id, name, started_at, baseline_started_at, baseline_completed_at "
                "FROM operational_epochs ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None
        except sqlite3.Error:
            return None
        finally:
            con.close()

    def event_summary(self) -> dict[str, Any]:
        """Event counts plus QC dispositions (Law: provenance + QC visibility)."""
        con = open_readonly(self.db_path)
        if con is None:
            return {}
        out: dict[str, Any] = {}
        try:
            if table_exists(con, "events"):
                out["events_total"] = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                out["events_by_status"] = {
                    r[0]: r[1] for r in con.execute(
                        "SELECT status, COUNT(*) FROM events GROUP BY status"
                    ).fetchall()
                }
                latest = con.execute("SELECT MAX(created_at) FROM events").fetchone()[0]
                out["latest_event_created_at"] = latest
            if table_exists(con, "event_reviews"):
                out["event_review_dispositions"] = {
                    r[0]: r[1] for r in con.execute(
                        "SELECT disposition, COUNT(*) FROM event_reviews GROUP BY disposition"
                    ).fetchall()
                }
            if table_exists(con, "specialist_lead_reviews"):
                out["lead_review_dispositions"] = {
                    r[0]: r[1] for r in con.execute(
                        "SELECT disposition, COUNT(*) FROM specialist_lead_reviews GROUP BY disposition"
                    ).fetchall()
                }
        except sqlite3.Error as exc:
            out["error"] = str(exc)
        finally:
            con.close()
        return out

    # -- health -------------------------------------------------------------

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
            if table_exists(con, "source_component_states"):
                cols = _columns(con, "source_component_states")
                ident = "source_id" if "source_id" in cols else "id"
                rows = fetchall(con, f"SELECT * FROM source_component_states ORDER BY {ident}")
                for row in rows:
                    keys = row.keys()
                    status_raw = row["health"] if "health" in keys else row["state"] if "state" in keys else None
                    sources.append(
                        SourceHealthEntry(
                            source_id=str(row[ident]),
                            status=_map_run_status(status_raw),
                            observed_count=row.get("observation_count") if "observation_count" in keys else None,
                            health_reason=status_raw,
                        )
                    )
            elif table_exists(con, "collector_runs"):
                cols = _columns(con, "collector_runs")
                src_col = "source_id" if "source_id" in cols else "collector_id"
                end_col = "finished_at" if "finished_at" in cols else "completed_at"
                rows = fetchall(
                    con,
                    f"""
                    SELECT {src_col} AS src, status, started_at AS started, {end_col} AS ended,
                           observation_count
                    FROM collector_runs
                    WHERE id IN (SELECT MAX(id) FROM collector_runs GROUP BY {src_col})
                    ORDER BY {src_col}
                    """,
                )
                for row in rows:
                    mapped = _map_run_status(row["status"])
                    ok = mapped == SourceHealthStatus.OK
                    sources.append(
                        SourceHealthEntry(
                            source_id=str(row["src"]),
                            status=mapped,
                            last_attempt_at=_parse_dt(row["started"]),
                            last_success_at=_parse_dt(row["ended"]) if ok else None,
                            observed_count=row["observation_count"],
                            health_reason=row["status"],
                        )
                    )
            else:
                warnings.append("no source-health tables present")
        except sqlite3.Error as exc:
            warnings.append(f"source health query issue: {exc}")
        finally:
            con.close()

        failed = sum(1 for s in sources if s.status in {SourceHealthStatus.FAILED, SourceHealthStatus.BLOCKED_ZERO})
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
        if con is None or not table_exists(con, "collector_runs"):
            return None
        try:
            cols = _columns(con, "collector_runs")
            src_col = "source_id" if "source_id" in cols else "collector_id"
            end_col = "finished_at" if "finished_at" in cols else "completed_at"
            obs = "observations_count" if "observations_count" in cols else (
                "observation_count" if "observation_count" in cols else None)
            sel = f"id, {src_col} AS source_key, status, started_at, {end_col} AS finished_at"
            if obs:
                sel += f", {obs} AS observations_count"
            if "is_baseline" in cols:
                sel += ", is_baseline"
            row = con.execute(f"SELECT {sel} FROM collector_runs ORDER BY id DESC LIMIT 1").fetchone()
            return dict(row) if row else None
        except sqlite3.Error:
            return None
        finally:
            con.close()

    def telemetry(self, *, limit: int = 20) -> list[TelemetryEnvelope]:
        con = open_readonly(self.db_path)
        if con is None or not table_exists(con, "collector_runs"):
            return []
        out: list[TelemetryEnvelope] = []
        try:
            cols = _columns(con, "collector_runs")
            src_col = "source_id" if "source_id" in cols else "collector_id"
            end_col = "finished_at" if "finished_at" in cols else "completed_at"
            obs = ("observations_count" if "observations_count" in cols
                   else "observation_count" if "observation_count" in cols
                   else "discovered_count")
            ev = "events_created"
            sel = f"id, {src_col} AS source_key, status, started_at, {end_col} AS finished_at, {obs}"
            if ev in cols:
                sel += f", {ev}"
            rows = fetchall(con, f"SELECT {sel} FROM collector_runs ORDER BY id DESC LIMIT ?", (limit,))
        except sqlite3.Error:
            return []
        for row in rows:
            keys = set(row.keys())
            out.append(
                TelemetryEnvelope(
                    clank_id=CLANK_ID,
                    run_id=str(row["id"]),
                    source_id=row["source_key"],
                    started_at=_parse_dt(row["started_at"]),
                    finished_at=_parse_dt(row["finished_at"]),
                    run_kind=RunKind.BASELINE_BUILD if ("is_baseline" in keys and row["is_baseline"]) else RunKind.NORMAL_RUN,
                    source_status=_map_run_status(row["status"]),
                    observed_count=row["observations_count"] if "observations_count" in keys else None,
                    event_count=row["events_created"] if "events_created" in keys else None,
                    delivery_count=None,  # not persisted by Watch — UNKNOWN, never zero-faked
                )
            )
        con.close()
        return out

    def qc_summary(self) -> dict[str, Any] | None:
        summary = self.event_summary()
        if not summary:
            return None
        return {
            "dispositions": summary.get("event_review_dispositions", {}),
            "lead_dispositions": summary.get("lead_review_dispositions", {}),
        }


def _columns(con: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]


def row_str(row: Any, key: str) -> str:
    try:
        return str(row[key])
    except Exception:
        return "unknown"
