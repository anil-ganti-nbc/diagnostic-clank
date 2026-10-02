"""Read-only Board schema-v3 observer (surface 0.2, COPS-000074).

The two summary methods preserve ``board_clank.observer`` at 613c3a1:
source_summary is a policy roster, and diagnostic_summary groups durable
uncertainty. Neither is collection health or market novelty. Richer evidence
lives in observer_evidence payload_version 1.0, never in extra summary keys.

Only sealed DELETE-mode snapshots are accepted. Snapshot manifest 1.0 intake
is the caller's responsibility: this adapter does not refresh, migrate,
collect, enable, deliver, resolve conditions, or establish deployment truth.
The child build, historical event revision, adapter revision and externally
observed deployment revision remain separate evidence.
"""

from __future__ import annotations

import math
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from clank_runtime.contracts.adapter import AdapterCapabilities, AdapterDescriptor, AdapterStatus
from clank_runtime.contracts.enums import OperationalState, ReleaseChannel, SourceHealthStatus
from clank_runtime.contracts.health import HealthPayload, SourceHealthEntry
from clank_runtime.version import ADAPTER_CONTRACT_VERSION

CLANK_ID = "board-clank"
OBSERVER_CONTRACT_VERSION = "0.2"
OBSERVER_EVIDENCE_VERSION = "1.0"
EXPECTED_SCHEMA_VERSION = 3
UNKNOWN = "UNKNOWN"

# Table names are the native 613c3a1 compatibility barrier. Columns below
# specify only the observer's projections; no collector/domain rules live here.
_TABLES = (
    "schema_migrations",
    "vendors",
    "board_families",
    "socs",
    "boards",
    "board_revisions",
    "board_variants",
    "sources",
    "source_baselines",
    "collector_runs",
    "canonical_observations",
    "observation_occurrences",
    "current_entity_observations",
    "events",
    "notifications",
    "delivery_policy",
    "processed_run_receipts",
    "run_errors",
    "board_classifications",
    "novelty_evidence",
    "price_observations",
    "software_support",
    "diagnostic_conditions",
    "diagnostic_sightings",
)
_COLUMNS = {
    "sources": "source_key vendor plane authority enabled promotion_state registered_state",
    "collector_runs": (
        "run_id source_key collector_key started_at finished_at status fixture_scenario error"
    ),
    "processed_run_receipts": (
        "run_id source_key receipt_hash accepted_at observation_count event_count"
    ),
    "source_baselines": "source_key baseline_run_id established_at observation_count",
    "run_errors": "error_id run_id source_key message created_at",
    "events": (
        "event_id event_key event_type source_key run_id baseline_silent "
        "payload_json created_at code_revision"
    ),
    "diagnostic_conditions": (
        "condition_key source_key plane diagnostic_type entity_key reason state_hash "
        "status first_observed_at first_run_id last_observed_at last_run_id resolved_at "
        "resolved_run_id open_occurrences total_occurrences transition_count"
    ),
    "diagnostic_sightings": (
        "sighting_id condition_key run_id source_key observed_at state_hash emitted_event_key"
    ),
}
_RUN_FIELDS = _COLUMNS["collector_runs"].replace(" ", ", ")
_DETAIL_LIMIT = 1000


def _time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(UTC) if parsed.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def _rows(con: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in con.execute(sql, params).fetchall()]


class BoardClankAdapter:
    def __init__(
        self,
        *,
        db_path: Path | str,
        observed_at: datetime | None = None,
        execution_freshness_hours: float = 24.0,
    ) -> None:
        self.db_path = Path(db_path)
        if (
            isinstance(execution_freshness_hours, bool)
            or not isinstance(execution_freshness_hours, int | float)
            or not math.isfinite(execution_freshness_hours)
            or execution_freshness_hours <= 0
        ):
            raise ValueError("execution freshness horizon must be a finite positive number")
        if observed_at is not None and observed_at.tzinfo is None:
            raise ValueError("observed_at must have a timezone")
        self.observed_at = observed_at
        # An observation age policy, not a claim that a scheduler exists.
        self.execution_freshness_hours = execution_freshness_hours

    def _now(self) -> datetime:
        return (self.observed_at or datetime.now(UTC)).astimezone(UTC)

    def _view(self) -> dict[str, Any]:
        view: dict[str, Any] = {
            "available": False,
            "schema_version": None,
            "reason": "database missing",
        }
        con = None
        try:
            if not self.db_path.is_file():
                return view
            # immutable=1 is safe only after rejecting WAL/rollback state;
            # it prevents SQLite creating sidecars even in writable test dirs.
            if any(
                Path(str(self.db_path) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")
            ):
                view["reason"] = "snapshot has SQLite sidecars"
                return view
            with self.db_path.open("rb") as handle:
                header = handle.read(100)
            if (
                len(header) < 100
                or header[:16] != b"SQLite format 3\x00"
                or header[18:20] != b"\x01\x01"
            ):
                view["reason"] = "snapshot is not a sealed DELETE-mode SQLite database"
                return view
            con = sqlite3.connect(
                self.db_path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True
            )
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA query_only=ON")
            if [row[0] for row in con.execute("PRAGMA quick_check")] != ["ok"]:
                view["reason"] = "snapshot integrity check failed"
                return view
            tables = {
                row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            if "schema_migrations" not in tables:
                view["reason"] = "schema_migrations missing"
                return view
            row = con.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
            view["schema_version"] = row[0]
            if row[0] != EXPECTED_SCHEMA_VERSION:
                view["reason"] = "unsupported or unstamped Board schema; expected 3"
                return view
            # Preserve native roster/summary evidence even when another
            # substrate is missing. Partial evidence never upgrades core
            # compatibility or health, and explicit availability accompanies it.
            try:
                view["sources"] = _rows(
                    con,
                    "SELECT "
                    + _COLUMNS["sources"].replace(" ", ", ")
                    + " FROM sources ORDER BY source_key",
                )
                view["source_summary_available"] = True
            except sqlite3.Error:
                pass
            try:
                grouped = _rows(
                    con,
                    "SELECT source_key, diagnostic_type, status, reason, COUNT(*) AS n "
                    "FROM diagnostic_conditions "
                    "GROUP BY source_key, diagnostic_type, status, reason "
                    "ORDER BY source_key, diagnostic_type, status",
                )
                try:
                    total = con.execute("SELECT COUNT(*) FROM diagnostic_sightings").fetchone()[0]
                except sqlite3.Error:
                    total = UNKNOWN
                view["diagnostic_summary"] = {"conditions": grouped, "sightings_total": total}
                view["diagnostic_summary_available"] = total != UNKNOWN
            except sqlite3.Error:
                pass
            missing = sorted(set(_TABLES) - tables)
            if missing:
                view["reason"] = "missing native tables: " + ", ".join(missing)
                return view
            for table, fields in _COLUMNS.items():
                columns = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
                missing = sorted(set(fields.split()) - columns)
                if missing:
                    view["reason"] = f"missing {table} columns: " + ", ".join(missing)
                    return view
            if con.execute("PRAGMA foreign_key_check").fetchone() is not None:
                view["reason"] = "snapshot foreign-key check failed"
                return view
            sources = view["sources"]
            if any(
                not isinstance(source["source_key"], str)
                or not source["source_key"].strip()
                or source["enabled"] not in (0, 1)
                for source in sources
            ):
                view["reason"] = "invalid native source policy identity or enabled state"
                return view
            runs = _rows(
                con,
                f"SELECT {_RUN_FIELDS} FROM collector_runs "
                "ORDER BY started_at DESC, rowid DESC LIMIT 20",
            )
            source_evidence = []
            for source in sources:
                key = source["source_key"]
                latest = _rows(
                    con,
                    f"SELECT {_RUN_FIELDS} FROM collector_runs "
                    "WHERE source_key=? ORDER BY started_at DESC, rowid DESC LIMIT 1",
                    (key,),
                )
                accepted = _rows(
                    con,
                    f"SELECT {_RUN_FIELDS} FROM collector_runs "
                    "WHERE source_key=? AND status='accepted' "
                    "ORDER BY started_at DESC, rowid DESC LIMIT 1",
                    (key,),
                )
                receipt = (
                    _rows(
                        con,
                        "SELECT "
                        + _COLUMNS["processed_run_receipts"].replace(" ", ", ")
                        + " FROM processed_run_receipts WHERE run_id=? AND source_key=?",
                        (accepted[0]["run_id"], key),
                    )
                    if accepted
                    else []
                )
                baseline = _rows(
                    con,
                    "SELECT "
                    + _COLUMNS["source_baselines"].replace(" ", ", ")
                    + " FROM source_baselines WHERE source_key=?",
                    (key,),
                )
                errors = _rows(
                    con,
                    "SELECT "
                    + _COLUMNS["run_errors"].replace(" ", ", ")
                    + " FROM run_errors WHERE source_key=? ORDER BY error_id DESC LIMIT 20",
                    (key,),
                )
                source_evidence.append(
                    {
                        "source_key": key,
                        "policy": dict(source),
                        "latest_attempt": latest[0] if latest else None,
                        "latest_accepted_run": accepted[0] if accepted else None,
                        "latest_accepted_receipt": receipt[0] if receipt else None,
                        "baseline": baseline[0] if baseline else None,
                        "recent_errors": errors,
                        "evidence_state": "RECORDED" if latest else UNKNOWN,
                        "missing_reason": None if latest else "no native collector run",
                        "provenance": [
                            "sources",
                            "collector_runs",
                            "processed_run_receipts",
                            "source_baselines",
                            "run_errors",
                        ],
                    }
                )
            condition_total = con.execute("SELECT COUNT(*) FROM diagnostic_conditions").fetchone()[
                0
            ]
            sighting_total = con.execute("SELECT COUNT(*) FROM diagnostic_sightings").fetchone()[0]
            conditions = _rows(
                con,
                "SELECT "
                + _COLUMNS["diagnostic_conditions"].replace(" ", ", ")
                + " FROM diagnostic_conditions ORDER BY condition_key LIMIT ?",
                (_DETAIL_LIMIT,),
            )
            sightings = _rows(
                con,
                "SELECT "
                + _COLUMNS["diagnostic_sightings"].replace(" ", ", ")
                + " FROM diagnostic_sightings ORDER BY sighting_id DESC LIMIT ?",
                (_DETAIL_LIMIT,),
            )
            latest_event = _rows(
                con,
                "SELECT "
                + _COLUMNS["events"].replace(" ", ", ")
                + " FROM events ORDER BY event_id DESC LIMIT 1",
            )
            diagnostic_events = _rows(
                con,
                "SELECT "
                + ", ".join("e." + field for field in _COLUMNS["events"].split())
                + " FROM events e WHERE e.event_key IN "
                "(SELECT emitted_event_key FROM diagnostic_sightings "
                "WHERE emitted_event_key IS NOT NULL) "
                "OR e.event_type='DIAGNOSTIC_RESOLVED' ORDER BY e.event_id DESC LIMIT ?",
                (_DETAIL_LIMIT,),
            )
            event_counts = _rows(
                con,
                "SELECT event_type, baseline_silent, COUNT(*) AS n FROM events "
                "GROUP BY event_type, baseline_silent ORDER BY event_type, baseline_silent",
            )
            view.update(
                available=True,
                reason="compatible sealed Board schema 3",
                sources=sources,
                runs=runs,
                source_evidence=source_evidence,
                diagnostics={
                    "conditions": conditions,
                    "sightings": list(reversed(sightings)),
                    "condition_total": condition_total,
                    "sightings_total": sighting_total,
                    "conditions_truncated": condition_total > len(conditions),
                    "sightings_truncated": sighting_total > len(sightings),
                    "recent_transition_events": diagnostic_events,
                    "transition_events_limit": _DETAIL_LIMIT,
                    "provenance": ["diagnostic_conditions", "diagnostic_sightings", "events"],
                },
                latest_event=latest_event[0] if latest_event else None,
                event_counts=event_counts,
            )
            return view
        except (OSError, sqlite3.Error, ValueError, TypeError):
            # A secret-safe category, never raw connection/config details.
            view["reason"] = "snapshot or native schema unreadable"
            return view
        finally:
            if con is not None:
                con.close()

    def identity(self) -> AdapterDescriptor:
        return AdapterDescriptor(
            contract_version=ADAPTER_CONTRACT_VERSION,
            clank_id=CLANK_ID,
            clank_version="0.1.0",
            release_channel=ReleaseChannel.EXPERIMENTAL,
            display_name="Board Clank",
            capabilities=self.capabilities(),
            description=(
                "Read-only experimental SBC shadow observation; "
                "instance/lane bound by snapshot manifest"
            ),
        )

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_identity=True,
            supports_status=True,
            supports_health=True,
            supports_last_run=True,
            supports_version=True,
        )

    def _freshness(self, run: dict[str, Any] | None) -> str:
        stamp = _time((run or {}).get("finished_at") or (run or {}).get("started_at"))
        if stamp is None:
            return UNKNOWN
        age = self._now() - stamp
        if age < timedelta(0):
            return UNKNOWN
        return "STALE" if age > timedelta(hours=self.execution_freshness_hours) else "FRESH"

    def _health(self, view: dict[str, Any]) -> HealthPayload:
        now = self._now()
        if not view["available"]:
            return HealthPayload(
                clank_id=CLANK_ID,
                overall_status=OperationalState.UNKNOWN,
                warnings=[view["reason"]],
                freshness="unknown",
                observed_at=now,
            )
        entries = []
        for evidence in view["source_evidence"]:
            source = evidence["policy"]
            run = evidence["latest_attempt"]
            accepted = evidence["latest_accepted_run"]
            fresh = self._freshness(run)
            failed = bool(run and run["status"] == "failed" and fresh == "FRESH")
            reason = (
                "latest native attempt failed"
                if failed
                else "native attempts do not establish current source coverage/health"
            )
            if not source["enabled"]:
                reason += "; source disabled by policy (not a collection failure)"
            entries.append(
                SourceHealthEntry(
                    source_id=source["source_key"],
                    status=SourceHealthStatus.FAILED if failed else SourceHealthStatus.UNKNOWN,
                    last_attempt_at=_time((run or {}).get("started_at")),
                    last_success_at=_time((accepted or {}).get("finished_at")),
                    health_reason=reason,
                    is_experimental=source["promotion_state"] == "EXPERIMENTAL",
                    extensions={
                        "enabled": source["enabled"],
                        "promotion_state": source["promotion_state"],
                        "native_execution_freshness": fresh,
                        "latest_attempt_status": (run or {}).get("status", UNKNOWN),
                        "latest_attempt_error": (run or {}).get("error"),
                        "evidence_provenance": "collector_runs; sources",
                    },
                )
            )
        latest = view["runs"][0] if view["runs"] else None
        freshness = self._freshness(latest)
        degraded = any(entry.status is SourceHealthStatus.FAILED for entry in entries)
        return HealthPayload(
            clank_id=CLANK_ID,
            overall_status=OperationalState.DEGRADED if degraded else OperationalState.UNKNOWN,
            sources=entries,
            last_attempt_at=_time((latest or {}).get("started_at")),
            freshness=freshness.lower(),
            observed_at=now,
            warnings=[
                "Current runtime/coverage not established by historical accepted runs",
                "Durable diagnostic uncertainty is not a source failure or market novelty",
            ],
            extensions={
                "diagnostic_summary": view["diagnostic_summary"],
                "scheduler_authority": "NONE",
                "delivery_authority": "NONE",
            },
        )

    def health(self) -> HealthPayload:
        return self._health(self._view())

    def status(self) -> AdapterStatus:
        view = self._view()
        health = self._health(view)
        latest = view.get("runs", [None])[0] if view.get("runs") else None
        return AdapterStatus(
            clank_id=CLANK_ID,
            operational_state=health.overall_status,
            release_channel=ReleaseChannel.EXPERIMENTAL,
            last_run_at=_time(
                (latest or {}).get("finished_at") or (latest or {}).get("started_at")
            ),
            is_stale=self._freshness(latest) != "FRESH",
            observed_at=self._now(),
            message=view["reason"] + "; runtime health and deployment require independent evidence",
            extensions={
                "native_schema_version": view["schema_version"],
                "deployment_state": UNKNOWN,
                "scheduler_authority": "NONE",
                "delivery_authority": "NONE",
            },
        )

    def last_run(self) -> dict[str, Any]:
        view = self._view()
        if not view["available"] or not view["runs"]:
            return {
                "supported": True,
                "evidence_state": UNKNOWN,
                "reason": view["reason"] if not view["available"] else "no native collector runs",
                "clock": "native_run_row",
                "derived_from": "collector_runs",
            }
        run = dict(view["runs"][0])
        run.update(
            supported=True,
            clock="native_run_row",
            derived_from="collector_runs",
            execution_result={
                "accepted": "APPLICATION_SUCCESS",
                "failed": "APPLICATION_FAILED",
            }.get(run["status"], UNKNOWN),
        )
        return run

    def schema_revision(self) -> str | None:
        version = self._view()["schema_version"]
        return str(version) if version is not None else None

    def code_revision(self) -> str:
        """Historical latest-event revision only; never current deployed HEAD."""
        return (self._view().get("latest_event") or {}).get("code_revision") or UNKNOWN

    def recent_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._view().get("runs", [])[: max(0, min(int(limit), 20))]

    def source_summary(self) -> list[dict[str, Any]]:
        """Exact native 613c3a1 roster shape; [] alone does not prove availability."""
        return self._view().get("sources", [])

    def diagnostic_summary(self) -> dict[str, Any]:
        """Exact native grouped-condition shape; missing evidence is not zero."""
        return self._view().get(
            "diagnostic_summary", {"conditions": [], "sightings_total": UNKNOWN}
        )

    def capability_states(self) -> dict[str, dict[str, str]]:
        view = self._view()
        proven = "active" if view["available"] else "unknown_or_unverified"
        sources = view.get("sources", [])
        collection = (
            "supported_unconfigured"
            if sources and all(not s["enabled"] for s in sources)
            else "unknown_or_unverified"
        )
        return {
            "collection": {
                "state": collection,
                "evidence": "sources.enabled policy; observer has no collection authority",
            },
            "health": {"state": proven, "evidence": view["reason"]},
            "events": {
                "state": proven,
                "evidence": (
                    "native events; baseline silence is preserved, FIRST_SEEN is not market novelty"
                ),
            },
            "diagnostics": {
                "state": proven,
                "evidence": (
                    "native diagnostic_conditions and diagnostic_sightings; no closure authority"
                ),
            },
            "continuity": {
                "state": proven,
                "evidence": "native source_baselines and processed_run_receipts",
            },
            "survivability": {
                "state": "unknown_or_unverified",
                "evidence": (
                    "native backup/restore support; current NAS backup/restore proof "
                    "is external to this snapshot"
                ),
            },
            "deployment": {
                "state": "unknown_or_unverified",
                "evidence": (
                    "child deployed revision/runtime state require independent host evidence"
                ),
            },
            "delivery": {
                "state": "unsupported_by_policy",
                "evidence": "Board outbox-only contract; no sender authority",
            },
            "scheduler_trace": {
                "state": "unsupported_by_policy",
                "evidence": "Board declares scheduler_authority NONE; observer does not schedule",
            },
            "qc": {"state": "unsupported", "evidence": "no qualified Board QC substrate"},
        }

    def observer_evidence(self) -> dict[str, Any]:
        """Versioned native evidence, independent of the exact native summaries.

        Null run/receipt/baseline means no such row was observed. Availability
        is explicit so missing tables cannot masquerade as empty healthy state.
        Conditions/sightings are bounded with counts and truncation markers.
        Manifest lineage supplies independent host source/deployment facts.
        """
        view = self._view()
        return {
            "payload_version": OBSERVER_EVIDENCE_VERSION,
            "observer_contract_version": OBSERVER_CONTRACT_VERSION,
            "availability": {
                "state": "AVAILABLE" if view["available"] else UNKNOWN,
                "reason": view["reason"],
                "source_summary": "AVAILABLE" if view.get("source_summary_available") else UNKNOWN,
                "diagnostic_summary": "AVAILABLE"
                if view.get("diagnostic_summary_available")
                else UNKNOWN,
            },
            "schema": {"expected": EXPECTED_SCHEMA_VERSION, "observed": view["schema_version"]},
            "sources": view.get("source_evidence", []),
            "diagnostics": view.get(
                "diagnostics",
                {
                    "conditions": [],
                    "sightings": [],
                    "condition_total": UNKNOWN,
                    "sightings_total": UNKNOWN,
                },
            ),
            "events": {
                "counts": view.get("event_counts", []),
                "evidence_state": "RECORDED" if view["available"] else UNKNOWN,
                "interpretation": "native event taxonomy; no observer-created novelty",
            },
            "revisions": {
                "child_source_revision": UNKNOWN,
                "child_deployed_revision": UNKNOWN,
                "unavailable_reason": (
                    "not established by child database; "
                    "see independent snapshot manifest host evidence"
                ),
                "latest_event": view.get("latest_event"),
                "event_revision_provenance": (
                    "events ORDER BY event_id DESC; historical event producer only"
                ),
            },
            "freshness_policy": {
                "execution_horizon_hours": self.execution_freshness_hours,
                "clock": "collector_runs.finished_at or started_at",
                "scheduler_implied": False,
            },
            "authority": {
                "collection": False,
                "source_enable": False,
                "promotion": False,
                "scheduler": False,
                "delivery": False,
                "diagnostic_closure": False,
                "database_mutation": False,
            },
        }
