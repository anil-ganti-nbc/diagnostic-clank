"""Chinese Tech Wire read-only Fleet adapter (v0.3 onboarding dogfood).

Native semantics preserved from the canonical participant
(database/models.py, database/db.py):

- ``source_runs`` is an append-only NATIVE per-attempt run table:
  one row per attempted source per cycle, written regardless of findings.
  A successful attempt with articles_new=0 is legitimate healthy zero-work,
  NOT a failure and NOT a materialization gap.
- ``layer`` distinguishes NEWS / COMMUNITY / DOCUMENTARY evidence planes;
  these are never merged into single-source identities.
- ``notifications`` persists SENT Discord deliveries only (sent_at +
  discord_message_id). Suppressed/failed delivery outcomes are log-only in
  the participant, so DB-level delivery claims cover SENT exclusively.
- Schema versioning: custom column-add migrations, NO version table ->
  schema revision is UNKNOWN, never invented.
- No review/QC substrate -> unsupported (absence established by mapped
  table inventory).
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

CLANK_ID = "chinese-tech-wire"


def _parse_dt(value: Any) -> Any:
    if value is None:
        return None
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


class ChineseTechWireAdapter:
    def __init__(
        self,
        *,
        db_path: Path | str,
        clank_version: str = "0.0.1",
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
            display_name="Chinese Tech Wire",
            description="Chinese-language technology discovery across news/"
                        "community/documentary layers",
        )

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_identity=True,
            supports_status=True,
            supports_health=True,
            supports_last_run=True,
            supports_telemetry=True,
            # SENT deliveries persisted natively; suppressed/failed are
            # log-only, so full delivery ACCOUNTING is partial by design.
            supports_delivery_accounting=True,
            supports_version=True,
            supports_manual_run=False,
            supports_local_fallback=False,
        )

    # -- native execution substrate ---------------------------------------

    def _latest_source_runs(self, con: sqlite3.Connection) -> list[Any]:
        """Latest attempt row per (source, layer). Layers stay distinct."""
        return fetchall(
            con,
            "SELECT r.source, r.layer, r.success, r.articles_found, "
            "r.articles_new, r.parse_errors, r.request_errors, "
            "r.started_at, r.finished_at FROM source_runs r "
            "WHERE r.id = (SELECT MAX(r2.id) FROM source_runs r2 "
            "WHERE r2.source = r.source AND r2.layer = r.layer) "
            "ORDER BY r.source, r.layer")

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
            if table_exists(con, "source_runs"):
                for row in self._latest_source_runs(con):
                    ok = bool(row["success"])
                    sources.append(SourceHealthEntry(
                        source_id=f"{row['source']}[{row['layer']}]",
                        status=(SourceHealthStatus.OK if ok
                                else SourceHealthStatus.FAILED),
                        last_attempt_at=_parse_dt(row["started_at"]),
                        last_success_at=_parse_dt(row["finished_at"])
                        if ok else None,
                        observed_count=row["articles_new"],
                        health_reason=str(row["request_errors"])
                        if row["request_errors"] else None,
                    ))
            else:
                warnings.append("source_runs table absent")
        except sqlite3.Error as exc:
            warnings.append(f"source health query issue: {exc}")
        finally:
            con.close()

        failed = sum(1 for s in sources if s.status == SourceHealthStatus.FAILED)
        overall = OperationalState.HEALTHY
        if not sources:
            overall = OperationalState.WARNING
            warnings.append("no source_runs rows recorded")
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

    def last_run(self) -> dict[str, Any]:
        """Most recent NATIVE participant run row (any source/layer).
        Clock label: native_run_row - this is participant-persisted
        execution evidence, not a derived estimate."""
        con = open_readonly(self.db_path)
        if con is None:
            return {"supported": False, "reason": "database missing",
                    "finished_at": None, "status": None, "run_kind": None}
        try:
            if not table_exists(con, "source_runs"):
                return {"supported": False, "reason": "source_runs absent",
                        "finished_at": None, "status": None, "run_kind": None}
            row = con.execute(
                "SELECT id, source, layer, started_at, finished_at, success,"
                " articles_found, articles_new FROM source_runs "
                "ORDER BY COALESCE(finished_at, started_at) DESC LIMIT 1"
            ).fetchone()
            if not row:
                return {"supported": True, "reason": "no rows",
                        "finished_at": None, "status": None, "run_kind": None}
            ok = bool(row["success"])
            return {
                "supported": True,
                "run_id": str(row["id"]),
                "source_id": f"{row['source']}[{row['layer']}]",
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
                "status": ("ok" if ok else "failed"),
                "clock": "native_run_row",
                "articles_found": row["articles_found"],
                "articles_new": row["articles_new"],
                "run_kind": None,   # no baseline/run-kind concept in schema
            }
        except sqlite3.Error as exc:
            return {"supported": False, "reason": str(exc),
                    "finished_at": None, "status": None, "run_kind": None}
        finally:
            con.close()

    def recent_runs(self, *, limit: int = 20) -> dict[str, Any]:
        con = open_readonly(self.db_path)
        if con is None:
            return {"supported": False, "runs": [], "reason": "database missing"}
        try:
            if not table_exists(con, "source_runs"):
                return {"supported": False, "runs": [],
                        "reason": "source_runs table absent"}
            rows = fetchall(
                con,
                "SELECT source, layer, success, articles_found, articles_new,"
                " parse_errors, request_errors, started_at, finished_at "
                "FROM source_runs ORDER BY COALESCE(finished_at, started_at)"
                " DESC LIMIT ?", (limit,))
            runs = [{
                "source": r["source"], "layer": r["layer"],
                "success": bool(r["success"]),
                "articles_found": r["articles_found"],
                "articles_new": r["articles_new"],
                "started_at": r["started_at"], "finished_at": r["finished_at"],
            } for r in rows]
            return {"supported": True, "count": len(runs), "runs": runs,
                    "clock": "native_run_row"}
        except sqlite3.Error as exc:
            return {"supported": False, "runs": [], "reason": str(exc)}
        finally:
            con.close()

    # -- generation / delivery ---------------------------------------------

    def generation_summary(self) -> dict[str, Any]:
        con = open_readonly(self.db_path)
        if con is None:
            return {"available": False}
        try:
            out: dict[str, Any] = {"available": True}
            for t in ("articles", "story_clusters", "community_threads",
                      "community_posts", "documentary_records"):
                out[t] = (con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                          if table_exists(con, t) else None)
            return out
        finally:
            con.close()

    def delivery_summary(self) -> dict[str, Any]:
        """SENT deliveries are native rows. Suppressed/failed outcomes have
        NO DB substrate (log-only in the participant) and are reported as
        unsupported rather than inferred as zero."""
        con = open_readonly(self.db_path)
        if con is None:
            return {"supported": False, "sent_total": None,
                    "reason": "database missing"}
        try:
            if not table_exists(con, "notifications"):
                return {"supported": False, "sent_total": None,
                        "reason": "notifications table absent"}
            sent = con.execute(
                "SELECT COUNT(*) FROM notifications").fetchone()[0]
            return {
                "supported": True,
                "sent_total": sent,
                "suppressed_total": None,
                "failed_total": None,
                "note": ("only successful sends persist; suppressed/failed "
                         "delivery outcomes are log-only in the participant"),
            }
        finally:
            con.close()

    def eligible_count(self) -> dict[str, Any]:
        con = open_readonly(self.db_path)
        if con is None:
            return {"eligible_total": None}
        try:
            total = (con.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
                     if table_exists(con, "articles") else None)
            notified = (con.execute(
                "SELECT COUNT(*) FROM notifications").fetchone()[0]
                if table_exists(con, "notifications") else None)
            return {"eligible_total": total, "notified_total": notified}
        except sqlite3.Error:
            return {"eligible_total": None}
        finally:
            con.close()

    def schema_revision(self) -> str | None:
        """No version table exists in this schema (custom column-add
        migrations). Honest answer: UNKNOWN, never a fabricated number."""
        return None

    def capability_states(self) -> dict[str, dict[str, str]]:
        db_present = self.db_path.exists()
        return {
            "collection": {
                "state": "active" if db_present else "unknown_or_unverified",
                "evidence": f"store {'present' if db_present else 'absent'}: "
                            f"{self.db_path}",
            },
            "health": {
                "state": "active",
                "evidence": "source_runs latest attempt per (source, layer)",
            },
            "events": {
                "state": "active",
                "evidence": "articles/story_clusters/community/documentary "
                            "substrates",
            },
            "delivery": {
                "state": "active",
                "evidence": "notifications table persists SENT deliveries; "
                            "suppressed/failed outcomes are log-only "
                            "(accounting partial by participant design)",
            },
            "qc": {
                "state": "unsupported",
                "evidence": "no review/QC substrate in mapped schema",
            },
            "scheduler_trace": {
                "state": "supported_unconfigured",
                "evidence": "P-4 trace plane consumes probe records when "
                            "present",
            },
            "continuity": {
                "state": "unknown_or_unverified",
                "evidence": "CONTIGUOUS presumed from absence of recorded "
                            "incidents - not yet operator-proven",
            },
            "survivability": {
                "state": "unknown_or_unverified",
                "evidence": "no backup evidence records registered for this "
                            "lane",
            },
            "baseline_run_kind": {
                "state": "unsupported",
                "evidence": "no baseline/run-kind columns in schema",
            },
        }
