"""Semiconductor Intelligence read-only Fleet adapter (first hard v0.3
extension dogfood).

Native subject model preserved from canonical participant source
(semi_intel/domain/models.py):

- The atomic unit is a **Claim** - a falsifiable, trackable assertion with
  native lifecycle events (claim_events, append-only) and a NATIVE 0..1
  confidence float. Motherclank observes these values as participant-native
  evidence and NEVER adjudicates semiconductor truth.
- ``provider_runs`` is a NATIVE per-provider-pass execution table written
  for every collection pass regardless of findings (items_collected=0 is a
  legitimate successful pass) -> materialization_policy = ALWAYS at the
  provider-pass level.
- ``sources`` / ``source_reputation`` carry participant-native source
  quality semantics; scores are preserved verbatim in payloads and never
  normalized into observer confidence.
- Schema versioning: alembic_version.

Typed-evidence extension: this lane emits ``intelligence_assertion@1``
envelopes (generic fleet-wide type; not named after any participant).
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

CLANK_ID = "semiconductor-intelligence"

_PROVIDER_STATUS_MAP = {
    "ok": SourceHealthStatus.OK,
    "partial": SourceHealthStatus.DEGRADED,
    "failed": SourceHealthStatus.FAILED,
}


def _parse_dt(value: Any) -> Any:
    if value is None:
        return None
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


class SemiconductorIntelligenceAdapter:
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
            display_name="Semiconductor Intelligence",
            description="Claims-and-evidence intelligence platform; atomic "
                        "subject is a falsifiable assertion, not an article",
        )

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_identity=True,
            supports_status=True,
            supports_health=True,
            supports_last_run=True,
            supports_telemetry=True,
            supports_delivery_accounting=False,  # no delivery table mapped
            supports_version=True,
            supports_manual_run=False,
            supports_local_fallback=False,
        )

    # -- execution substrate (two distinct native planes) ------------------
    #
    # P-4.4: the live deployment proved these are DIFFERENT planes:
    #   operational_job_runs -> application-level scheduled job execution
    #                          (OperationalScheduler; trigger_type records
    #                          whether the scheduler fired)
    #   provider_runs        -> provider-collection attempt execution
    #                          (may legitimately be EMPTY forever when the
    #                          only configured source is manual)
    # Neither is derived from the other. Both are exposed separately.

    _JOB_STATUS_MAP = {
        "successful": SourceHealthStatus.OK,
        "partial": SourceHealthStatus.DEGRADED,
        "failed": SourceHealthStatus.FAILED,
    }

    def job_runs_recent(self, *, limit: int = 20) -> dict[str, Any]:
        """Native application-level scheduled job runs (newest first)."""
        con = open_readonly(self.db_path)
        if con is None:
            return {"supported": False, "runs": [], "reason": "database missing"}
        try:
            if not table_exists(con, "operational_job_runs"):
                return {"supported": False, "runs": [],
                        "reason": "operational_job_runs table absent"}
            rows = fetchall(
                con,
                "SELECT id, job_type, trigger_type, started_at, finished_at,"
                " status, attempt_number, error_summary FROM "
                "operational_job_runs "
                "ORDER BY COALESCE(finished_at, started_at) DESC LIMIT ?",
                (limit,))
            runs = [{
                "run_id": str(r["id"]),
                "job_type": r["job_type"],
                "trigger_type": r["trigger_type"],
                "started_at": r["started_at"],
                "finished_at": r["finished_at"],
                "status": (r["status"] or "unknown").lower(),
                "attempt_number": r["attempt_number"],
                "error_summary": r["error_summary"],
            } for r in rows]
            return {"supported": True, "count": len(runs), "runs": runs,
                    "clock": "native_operational_job_run"}
        except sqlite3.Error as exc:
            return {"supported": False, "runs": [], "reason": str(exc)}
        finally:
            con.close()

    def provider_collection_summary(self) -> dict[str, Any]:
        """Provider-collection plane summary. Empty by design when every
        configured source is manual/polling-disabled - that is
        configuration truth, not breakage."""
        con = open_readonly(self.db_path)
        if con is None:
            return {"available": False}
        try:
            runs_present = table_exists(con, "provider_runs")
            sources_state = None
            if table_exists(con, "sources"):
                row = con.execute(
                    "SELECT COUNT(*) AS total, "
                "SUM(CASE WHEN polling_enabled THEN 1 ELSE 0 END) AS on_ "
                "FROM sources").fetchone()
                sources_state = {"total": row["total"] or 0,
                                 "polling_enabled": row["on_"] or 0}
            latest = None
            if runs_present:
                r = con.execute(
                    "SELECT MAX(COALESCE(finished_at, started_at)) AS m "
                    "FROM provider_runs").fetchone()
                latest = r["m"] if r else None
            return {"available": True, "runs_present": bool(runs_present),
                    "latest_activity": latest,
                    "sources": sources_state,
                    "note": ("empty provider plane with zero polling-enabled "
                             "sources is legitimate manual-only "
                             "configuration")}
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
        con = open_readonly(self.db_path)
        assert con is not None
        sources: list[SourceHealthEntry] = []
        warnings: list[str] = []
        try:
            if table_exists(con, "provider_runs"):
                rows = fetchall(
                    con,
                    "SELECT p.provider, p.status, p.items_collected, "
                    "p.error, p.started_at, p.finished_at FROM provider_runs p"
                    " WHERE p.id = (SELECT MAX(p2.id) FROM provider_runs p2"
                    " WHERE p2.provider = p.provider) ORDER BY p.provider")
                for row in rows:
                    raw = (row["status"] or "unknown").lower()
                    mapped = _PROVIDER_STATUS_MAP.get(
                        raw, SourceHealthStatus.UNKNOWN)
                    sources.append(SourceHealthEntry(
                        source_id=row["provider"],
                        status=mapped,
                        last_attempt_at=_parse_dt(row["started_at"]),
                        last_success_at=_parse_dt(row["finished_at"])
                        if raw == "ok" else None,
                        observed_count=row["items_collected"],
                        health_reason=row["error"],
                    ))
            else:
                warnings.append("provider_runs table absent")

            # P-4.4: detect manual-only configuration while connection is
            # still open. Empty provider plane + zero polling-enabled
            # sources = legitimate configuration, not breakage.
            if table_exists(con, "sources"):
                src_row = con.execute(
                    "SELECT COUNT(*) AS total, "
                    "SUM(CASE WHEN polling_enabled THEN 1 ELSE 0 END) AS on_ "
                    "FROM sources").fetchone()
                if (src_row["total"] or 0) > 0 and \
                        (src_row["on_"] or 0) == 0:
                    warnings.append("__MANUAL_ONLY_SOURCE_CONFIG__")
        except sqlite3.Error as exc:
            warnings.append(f"execution query issue: {exc}")
        finally:
            con.close()

        failed = sum(1 for s in sources if s.status == SourceHealthStatus.FAILED)
        overall = OperationalState.HEALTHY
        if not sources:
            if any("__MANUAL_ONLY_SOURCE_CONFIG__" in w for w in warnings):
                overall = OperationalState.HEALTHY
                warnings.append("no provider_runs rows: manual-only source "
                                "configuration - legitimate")
            else:
                overall = OperationalState.WARNING
                warnings.append("no provider_runs rows recorded")
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
        """Freshest NATIVE execution evidence with the substrate chosen
        deterministically - never whichever table happens to have rows.

        Primary substrate: operational_job_runs (application-level scheduled
        execution - the plane the scheduler cadence measures).
        Secondary: provider_runs (collection attempts), used only when the
        job plane has no table/rows, and then EXPLICITLY labeled as a
        fallback so no consumer mistakes it for job execution.
        """
        con = open_readonly(self.db_path)
        if con is None:
            return {"supported": False, "reason": "database missing",
                    "finished_at": None, "status": None, "run_kind": None}
        try:
            job_row = None
            if table_exists(con, "operational_job_runs"):
                job_row = con.execute(
                    "SELECT id, job_type, trigger_type, started_at,"
                    " finished_at, status, attempt_number, error_summary "
                    "FROM operational_job_runs "
                    "ORDER BY COALESCE(finished_at, started_at) DESC LIMIT 1"
                ).fetchone()
            if job_row is not None:
                status_raw = (job_row["status"] or "unknown").lower()
                return {
                    "supported": True,
                    "run_id": str(job_row["id"]),
                    "source_id": f"job[{job_row['job_type']}]",
                    "started_at": job_row["started_at"],
                    "finished_at": job_row["finished_at"],
                    "status": status_raw,
                    "clock": "native_operational_job_run",
                    "substrate": "operational_job_runs",
                    "trigger_type": (job_row["trigger_type"] or "unknown"),
                    "attempt_number": job_row["attempt_number"],
                    "error_summary": job_row["error_summary"],
                    "provider_plane": self.provider_collection_summary(),
                    # zero collected items is legitimate on either plane;
                    # never inferred as failure from counts alone
                    "zero_items_note": ("zero work may be legitimate due to "
                                        "due-gating/manual configuration"),
                    "run_kind": None,
                }
            # Fallback plane, visibly labeled as fallback:
            if table_exists(con, "provider_runs"):
                row = con.execute(
                    "SELECT id, provider, started_at, finished_at,"
                    " items_collected, status, error FROM provider_runs "
                    "ORDER BY COALESCE(finished_at, started_at) DESC LIMIT 1"
                ).fetchone()
                if row:
                    return {
                        "supported": True,
                        "run_id": str(row["id"]),
                        "source_id": f"provider[{row['provider']}]",
                        "started_at": row["started_at"],
                        "finished_at": row["finished_at"],
                        "status": ((row["status"] or "unknown").lower()),
                        "clock": "native_provider_run",
                        "substrate": "provider_runs",
                        "fallback": True,
                        "fallback_note": ("job-plane absent; provider-run "
                                          "recency used as execution "
                                          "evidence"),
                        "items_collected": row["items_collected"],
                        "error": row["error"],
                        "run_kind": None,
                    }
            return {"supported": True, "reason": "no rows",
                    "finished_at": None, "status": None, "run_kind": None}
        except sqlite3.Error as exc:
            return {"supported": False, "reason": str(exc),
                    "finished_at": None, "status": None, "run_kind": None}
        finally:
            con.close()

    # -- domain substrate (observed, never adjudicated) --------------------

    def claims_summary(self) -> dict[str, Any]:
        """Participant-native assertion counts by status. These are SI
        domain facts, NOT Motherclank truth judgments."""
        con = open_readonly(self.db_path)
        if con is None or not table_exists(con, "claims"):
            return {"available": False, "by_status": {}}
        try:
            rows = fetchall(con, "SELECT status, COUNT(*) AS n FROM claims "
                                 "GROUP BY status ORDER BY status")
            by_status = {(r["status"] or "unknown").lower(): r["n"]
                         for r in rows}
            total = sum(by_status.values())
            return {"available": True, "total_claims": total,
                    "by_status": by_status,
                    "note": ("participant-native claim statuses; confidence "
                             "values are participant-native 0..1 floats and "
                             "are NOT observer truth judgments")}
        except sqlite3.Error as exc:
            return {"available": False, "by_status": {}, "reason": str(exc)}
        finally:
            con.close()

    def schema_revision(self) -> str | None:
        con = open_readonly(self.db_path)
        if con is None or not table_exists(con, "alembic_version"):
            return None
        try:
            row = con.execute(
                "SELECT version_num FROM alembic_version LIMIT 1").fetchone()
            return row[0] if row else None
        except sqlite3.Error:
            return None
        finally:
            con.close()

    def capability_states(self) -> dict[str, dict[str, str]]:
        db_present = self.db_path.exists()
        con = open_readonly(self.db_path) if db_present else None
        has_provider = has_claims = has_alembic = False
        if con is not None:
            try:
                has_provider = table_exists(con, "provider_runs")
                has_claims = table_exists(con, "claims")
                has_alembic = table_exists(con, "alembic_version")
            finally:
                con.close()
        act = "active" if db_present else "unknown_or_unverified"
        return {
            "collection": {"state": act,
                           "evidence": f"provider_runs substrate, store "
                                       f"{'present' if db_present else 'absent'}"},
            "health": {"state": "active",
                       "evidence": "application plane: operational_job_runs; provider plane: latest pass per provider"},
            "events": {"state": "active" if has_claims
                       else "unknown_or_unverified",
                       "evidence": "claims/assertions are the native subject "
                                   "(participant domain, not observer claims)"},
            "delivery": {"state": "unsupported_by_policy",
                         "evidence": "no delivery substrate mapped in this "
                                     "observer surface"},
            "qc": {"state": "unknown_or_unverified",
                   "evidence": "editorial layer exists in participant but no "
                               "review substrate mapped yet"},
            "scheduler_trace": {"state": "supported_unconfigured",
                                "evidence": "OperationalScheduler path; "
                                            "ACT-003 invocation-path proof "
                                            "still OPEN"},
            "continuity": {"state": "unknown_or_unverified",
                           "evidence": "no destructive incident recorded; "
                                       "continuity unproven, not presumed"},
            "survivability": {"state": "unknown_or_unverified",
                              "evidence": "operations/backup exists in "
                                          "participant code; no backup "
                                          "evidence records registered here"},
            "baseline_run_kind": {"state": "unsupported",
                                  "evidence": "no baseline/run-kind columns "
                                              "in schema"},
        }
