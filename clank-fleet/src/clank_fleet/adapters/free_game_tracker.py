"""Free Game Tracker read-only Fleet adapter.

Onboarded via the registry-driven observer plane (hot-swap law): Motherclank
core carries no FGT-specific logic.

Native semantics preserved (from the canonical newsroom implementation):

- ``source_health`` is per-source LATEST outcome (source primary key):
  every attempted fetch records a row, and "zero games" is explicitly
  healthy (a quiet week) - last_count=0 with status ok.
- There is NO participant run table. Execution currency is derived from
  MAX(source_health.last_attempt_at / last_success_at); that derivation is
  labeled in the payload, never presented as a native run row.
- Discord delivery accounting (DeliveryOutcome: posted / no_events /
  no_eligible_events / webhook_not_configured / payload_construction_failed
  / delivery_failed) is LOG-ONLY in the participant - it is not persisted
  to this datastore, so DB-level delivery claims stop at unsupported and
  never borrow from logs.
- Generation substrates: news_events (event_key unique), new_releases,
  steam_deals - each counted independently.
- Schema versioning: alembic_version.
- No review/QC substrate observed -> unsupported, not unknown-by-laziness:
  absence is established by the mapped table inventory.
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

CLANK_ID = "free-game-tracker"


def _parse_dt(value: Any) -> Any:
    if value is None:
        return None
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


class FreeGameTrackerAdapter:
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

    # -- identity ---------------------------------------------------------

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
            display_name="Free Game Tracker",
            description="Newly-free PC game discovery across storefront "
                        "sources with quality gating and selective Discord "
                        "delivery",
        )

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_identity=True,
            supports_status=True,
            supports_health=True,
            supports_last_run=False,   # no run table; see execution_evidence
            supports_telemetry=True,
            supports_delivery_accounting=False,  # outcomes are log-only
            supports_version=True,
            supports_manual_run=False,
            supports_local_fallback=False,
        )

    # -- store helpers ----------------------------------------------------

    def _table_counts(self, con: sqlite3.Connection,
                      tables: tuple[str, ...]) -> dict[str, int]:
        out: dict[str, int] = {}
        for t in tables:
            if table_exists(con, t):
                try:
                    out[t] = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                except sqlite3.Error:
                    out[t] = None
        return out

    # -- observer surface -------------------------------------------------

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
        sources: list[SourceHealthEntry] = []
        warnings: list[str] = []
        try:
            if table_exists(con, "source_health"):
                rows = fetchall(
                    con,
                    "SELECT source, last_attempt_at, last_success_at, "
                    "last_status, last_count, last_error "
                    "FROM source_health ORDER BY source")
                for row in rows:
                    ok = row["last_status"] == "ok"
                    sources.append(SourceHealthEntry(
                        source_id=row["source"],
                        status=(SourceHealthStatus.OK if ok
                                else SourceHealthStatus.FAILED),
                        last_attempt_at=_parse_dt(row["last_attempt_at"]),
                        last_success_at=_parse_dt(row["last_success_at"]),
                        observed_count=row["last_count"],
                        health_reason=row["last_error"],
                    ))
            else:
                warnings.append("source_health table absent")
        except sqlite3.Error as exc:
            warnings.append(f"source health query issue: {exc}")
        finally:
            con.close()

        failed = sum(1 for s in sources if s.status.value == "failed")
        overall = OperationalState.HEALTHY
        if not sources:
            overall = OperationalState.WARNING
            warnings.append("no source_health rows recorded")
        elif failed == len(sources):
            overall = OperationalState.FAILED
        elif failed:
            overall = OperationalState.DEGRADED

        last_success = max((s.last_success_at for s in sources
                            if s.last_success_at), default=None)
        last_attempt = max((s.last_attempt_at for s in sources
                            if s.last_attempt_at), default=None)
        return HealthPayload(
            clank_id=CLANK_ID,
            overall_status=overall,
            sources=sources,
            last_success_at=last_success,
            last_attempt_at=last_attempt or now,
            warnings=warnings,
            is_stale_cache=False,
            observed_at=now,
        )

    def last_run(self) -> dict[str, Any]:
        """FGT has NO run table. Execution currency derives from
        source_health; that derivation is labeled, never disguised as a
        native run row."""
        con = open_readonly(self.db_path)
        if con is None:
            return {"supported": False,
                    "reason": "database missing",
                    "finished_at": None, "status": None, "run_kind": None}
        try:
            if not table_exists(con, "source_health"):
                return {"supported": False,
                        "reason": "source_health table absent",
                        "finished_at": None, "status": None, "run_kind": None}
            row = con.execute(
                "SELECT MAX(last_attempt_at) AS a FROM source_health"
            ).fetchone()
            latest = row["a"] if row else None
            if latest is None:
                return {"supported": True, "reason": "no rows",
                        "finished_at": None, "status": None, "run_kind": None}
            failed_row = con.execute(
                "SELECT COUNT(*) AS n FROM source_health "
                "WHERE last_status='error' AND last_attempt_at = "
                "(SELECT MAX(last_attempt_at) FROM source_health)"
            ).fetchone()["n"]
            return {
                "supported": True,
                "run_id": None,
                "status": ("failed" if failed_row else "ok"),
                "finished_at": latest,
                "started_at": None,
                "run_kind": None,   # no baseline/run-kind concept in FGT
                "derived_from": "MAX(source_health.last_attempt_at)",
            }
        except sqlite3.Error as exc:
            return {"supported": False, "reason": str(exc),
                    "finished_at": None, "status": None, "run_kind": None}
        finally:
            con.close()

    def execution_evidence(self) -> dict[str, Any]:
        """Per-source recency substrate: proves whether each attempted
        source left fresh evidence, independent of any run row."""
        con = open_readonly(self.db_path)
        if con is None:
            return {"available": False, "sources": {}}
        try:
            rows = fetchall(
                con,
                "SELECT source, last_attempt_at, last_success_at, "
                "last_status, last_count FROM source_health ORDER BY source")
            return {"available": True,
                    "sources": {r["source"]: {
                        "last_attempt_at": r["last_attempt_at"],
                        "last_success_at": r["last_success_at"],
                        "last_status": r["last_status"],
                        "last_count": r["last_count"],
                    } for r in rows}}
        except sqlite3.Error:
            return {"available": False, "sources": {}}
        finally:
            con.close()

    def generation_summary(self) -> dict[str, Any]:
        """Generation substrates counted independently - discovery counts
        are never conflated with delivery."""
        con = open_readonly(self.db_path)
        if con is None:
            return {"available": False}
        try:
            counts = self._table_counts(
                con, ("news_events", "new_releases", "steam_deals"))
            return {"available": True, **counts}
        finally:
            con.close()

    def delivery_summary(self) -> dict[str, Any]:
        """DeliveryOutcome accounting (posted/no_events/no_eligible_events/
        webhook_not_configured/payload_construction_failed/delivery_failed)
        is LOG-ONLY in the participant. This datastore cannot support
        delivery claims; logs belong to the probe plane, never inferred."""
        if not self.db_path.exists():
            return {"supported": False, "by_outcome": {},
                    "reason": "database missing"}
        return {"supported": False, "by_outcome": {},
                "reason": "delivery outcomes are log-only in the "
                          "participant (notify.py DeliveryResult); no "
                          "delivery table exists"}

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
        has_sources = has_generation = has_alembic = False
        if con is not None:
            try:
                has_sources = table_exists(con, "source_health")
                has_generation = table_exists(con, "news_events")
                has_alembic = table_exists(con, "alembic_version")
            finally:
                con.close()
        return {
            "collection": {
                "state": "active" if db_present else "unknown_or_unverified",
                "evidence": f"store {'present' if db_present else 'absent'}: "
                            f"{self.db_path}",
            },
            "health": {
                "state": "active" if has_sources else "unknown_or_unverified",
                "evidence": "source_health per-source latest outcome; zero "
                            "games is healthy by design",
            },
            "events": {
                "state": "active" if has_generation
                         else "unknown_or_unverified",
                "evidence": "news_events/new_releases/steam_deals generation "
                            "substrates",
            },
            "delivery": {
                "state": "unsupported",
                "evidence": "DeliveryOutcome accounting is log-only in the "
                            "participant; no delivery table exists in this "
                            "datastore",
            },
            "qc": {
                "state": "unsupported",
                "evidence": "no review/QC substrate in the mapped table "
                            "inventory",
            },
            "scheduler_trace": {
                "state": "supported_unconfigured",
                "evidence": "P-4 trace plane consumes probe records when "
                            "present",
            },
            "continuity": {
                "state": "active",
                "evidence": "no destructive incident recorded for this lane; "
                            "CONTIGUOUS unless registry says otherwise",
            },
            "survivability": {
                "state": "unknown_or_unverified",
                "evidence": "no backup evidence records registered for this "
                            "lane",
            },
            "baseline_run_kind": {
                "state": "unsupported_by_policy",
                "evidence": "no run table exists; baseline/run-kind concepts "
                            "do not apply to this datastore",
            },
        }
