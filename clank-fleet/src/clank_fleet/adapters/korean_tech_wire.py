"""Korean Tech Wire read-only Fleet adapter.

Phase 2C onboarding. KTW is a collection-only intelligence system by explicit
editorial policy (no events, no notifications), so this adapter exposes
source lifecycle, per-source run health (append-only source_run_health),
article throughput and feedback presence. Event/delivery capabilities are
reported as unsupported — that absence IS the domain truth.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from clank_fleet.adapters.base import fetchall, open_readonly, table_exists
from clank_fleet.adapters.feature_phone import _parse_dt
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

CLANK_ID = "korean-tech-wire"


class KoreanTechWireAdapter:
    def __init__(
        self,
        *,
        db_path: Path | str,
        clank_version: str = "0.0.1",
        release_channel: str = "soaking",
    ) -> None:
        self.db_path = Path(db_path)
        self.clank_version = clank_version
        self.release_channel = release_channel

    def identity(self) -> AdapterDescriptor:
        try:
            channel = ReleaseChannel(self.release_channel)
        except ValueError:
            channel = ReleaseChannel.SOAKING
        return AdapterDescriptor(
            contract_version=ADAPTER_CONTRACT_VERSION,
            clank_id=CLANK_ID,
            clank_version=self.clank_version,
            release_channel=channel,
            capabilities=self.capabilities(),
            display_name="Korean Tech Wire",
            description="Korean-language semiconductor/display news collection (no event lane by policy)",
        )

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_identity=True,
            supports_status=True,
            supports_health=True,
            supports_last_run=True,
            supports_telemetry=True,
            supports_delivery_accounting=False,  # no delivery exists by editorial policy
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
        last_finished = None
        con = open_readonly(self.db_path)
        assert con is not None
        try:
            if table_exists(con, "runs"):
                row = con.execute("SELECT MAX(finished_at) AS m FROM runs").fetchone()
                last_finished = _parse_dt(row["m"]) if row and row["m"] else None
        finally:
            con.close()
        return AdapterStatus(
            clank_id=CLANK_ID,
            operational_state=OperationalState.HEALTHY if last_finished else OperationalState.UNKNOWN,
            message="run history present" if last_finished else "no runs recorded",
            is_stale=last_finished is None,
            observed_at=now,
        )

    def schema_revision(self) -> int | None:
        con = open_readonly(self.db_path)
        if con is None or not table_exists(con, "schema_migrations"):
            return None
        try:
            row = con.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
            return row[0] if row else None
        except sqlite3.Error:
            return None
        finally:
            con.close()

    def source_lifecycle(self) -> list[dict[str, Any]]:
        """Declared promotion status per source (EXPERIMENTAL/PRODUCTION)."""
        con = open_readonly(self.db_path)
        if con is None or not table_exists(con, "sources"):
            return []
        try:
            rows = fetchall(con, "SELECT id, name, status, updated_at FROM sources ORDER BY id")
            return [dict(r) for r in rows]
        except sqlite3.Error:
            return []
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
            if table_exists(con, "source_run_health") and table_exists(con, "sources"):
                rows = fetchall(
                    con,
                    """
                    SELECT s.name AS source_name, s.status AS declared_status,
                           SUM(h.success) AS ok_runs,
                           SUM(CASE WHEN h.success = 0 THEN 1 ELSE 0 END) AS failed_runs,
                           MAX(h.attempted_at) AS last_attempted_at,
                           MAX(CASE WHEN h.success = 1 THEN h.attempted_at END) AS last_success_at,
                           SUM(h.new_articles) AS new_articles
                    FROM source_run_health h JOIN sources s ON s.id = h.source_id
                    GROUP BY s.id ORDER BY s.id
                    """,
                )
                for row in rows:
                    ok_runs = row["ok_runs"] or 0
                    failed_runs = row["failed_runs"] or 0
                    # Law-3 honest semantics: recency matters; historical success alone
                    # must not read HEALTHY forever.
                    last_ok = _parse_dt(row["last_success_at"])
                    if ok_runs == 0:
                        mapped = SourceHealthStatus.FAILED
                    elif failed_runs >= max(ok_runs * 4, 8):
                        mapped = SourceHealthStatus.DEGRADED
                    elif last_ok is None:
                        mapped = SourceHealthStatus.UNKNOWN
                    else:
                        mapped = SourceHealthStatus.OK
                    sources.append(
                        SourceHealthEntry(
                            source_id=str(row["source_name"]),
                            status=mapped,
                            last_attempt_at=_parse_dt(row["last_attempted_at"]),
                            last_success_at=last_ok,
                            observed_count=row["new_articles"],
                            health_reason=f"declared={row['declared_status']} ok={ok_runs} fail={failed_runs}",
                        )
                    )
            else:
                warnings.append("source_run_health/sources absent")
        except sqlite3.Error as exc:
            warnings.append(f"health query issue: {exc}")
        finally:
            con.close()

        failed = sum(1 for s in sources if s.status in {SourceHealthStatus.FAILED, SourceHealthStatus.BLOCKED_ZERO})
        overall = OperationalState.HEALTHY
        if not sources:
            overall = OperationalState.WARNING
            warnings.append("no per-source run health recorded")
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
        if con is None or not table_exists(con, "runs"):
            return None
        try:
            cols = [r[1] for r in con.execute("PRAGMA table_info(runs)")]
            order = "finished_at" if "finished_at" in cols else "id"
            row = con.execute(f"SELECT * FROM runs ORDER BY {order} DESC LIMIT 1").fetchone()
            return dict(row) if row else None
        except sqlite3.Error:
            return None
        finally:
            con.close()

    def telemetry(self, *, limit: int = 20) -> list[TelemetryEnvelope]:
        con = open_readonly(self.db_path)
        if con is None or not table_exists(con, "runs") or not table_exists(con, "source_run_health"):
            return []
        out: list[TelemetryEnvelope] = []
        try:
            rows = fetchall(
                con,
                """
                SELECT h.id, s.name AS source_name, h.success, h.attempted_at,
                       h.references_discovered, h.new_articles
                FROM source_run_health h JOIN sources s ON s.id = h.source_id
                ORDER BY h.id DESC LIMIT ?
                """,
                (limit,),
            )
            for row in rows:
                status = SourceHealthStatus.OK if row["success"] else SourceHealthStatus.FAILED
                out.append(
                    TelemetryEnvelope(
                        clank_id=CLANK_ID,
                        run_id=str(row["id"]),
                        source_id=row["source_name"],
                        started_at=_parse_dt(row["attempted_at"]),
                        finished_at=_parse_dt(row["attempted_at"]),
                        run_kind=RunKind.NORMAL_RUN,
                        source_status=status,
                        observed_count=row["references_discovered"],
                        event_count=None,  # no event lane by policy — null, not zero-faked
                        delivery_count=None,
                    )
                )
        finally:
            con.close()
        return out

    def article_summary(self) -> dict[str, Any]:
        con = open_readonly(self.db_path)
        if con is None:
            return {}
        out: dict[str, Any] = {}
        try:
            if table_exists(con, "articles"):
                out["articles_total"] = con.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
                out["latest_article_discovered_at"] = con.execute(
                    "SELECT MAX(discovered_at) FROM articles"
                ).fetchone()[0]
            if table_exists(con, "article_feedback"):
                out["feedback_rows"] = con.execute("SELECT COUNT(*) FROM article_feedback").fetchone()[0]
        except sqlite3.Error as exc:
            out["error"] = str(exc)
        finally:
            con.close()
        return out

    def eligible_count(self) -> dict[str, Any]:
        """M4.5 coverage: articles a human could give feedback on."""
        con = open_readonly(self.db_path)
        if con is None or not table_exists(con, "articles"):
            return {"eligible_total": None}
        try:
            return {"eligible_total": con.execute(
                "SELECT COUNT(*) FROM articles").fetchone()[0]}
        except sqlite3.Error:
            return {"eligible_total": None}
        finally:
            con.close()

    def qc_records(self, *, limit: int = 1000) -> list[dict[str, Any]]:
        """Row-level freeform article feedback (M4). The `outcome` value is
        freeform by design; it is preserved verbatim and fleet-normalization
        happens only where explicitly defensible."""
        con = open_readonly(self.db_path)
        if con is None or not table_exists(con, "article_feedback"):
            return []
        try:
            rows = fetchall(
                con,
                """
                SELECT id AS original_record_id, outcome AS raw_disposition,
                       article_id AS subject_id, note, created_at AS observed_at
                FROM article_feedback ORDER BY id LIMIT ?
                """,
                (limit,),
            )
            out = []
            for row in rows:
                rec = dict(row)
                rec["source_table"] = "article_feedback"
                rec["subject_type"] = "article"
                out.append(rec)
            return out
        except sqlite3.Error:
            return []
        finally:
            con.close()

    def qc_summary(self) -> dict[str, Any] | None:
        summary = self.article_summary()
        if "feedback_rows" not in summary:
            return {"dispositions": {}, "note": "feedback table absent"}
        return {"dispositions": {"freeform_feedback": summary["feedback_rows"]}}
