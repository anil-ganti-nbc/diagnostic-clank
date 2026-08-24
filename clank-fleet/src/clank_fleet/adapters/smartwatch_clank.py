"""Smartwatch Clank read-only Fleet adapter - SCHEMA-INTROSPECTION STAGE.

Status: interface + fixture contract COMPLETE; live semantic mapping
BLOCKED pending the real restored-DB schema (no table/column names have
been observed by the adapter author; none are invented here).

Until the live schema is mapped, this adapter deliberately refuses to
guess. It exposes only what sqlite metadata proves:

- identity / capabilities / schema-introspection inventory (table names +
  row counts via read-only counts)
- everything domain-specific (run health, source health, observations,
  baseline/run-kind, QC) is reported as UNKNOWN / empty with an explicit
  ``live_schema_validation`` marker of ``BLOCKED``

This keeps smartwatch-clank harvestable through the registry-driven
observer plane WITHOUT manufacturing operational claims - the incident
architecture's core rule applied to onboarding itself.
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
from clank_runtime.contracts.enums import OperationalState, ReleaseChannel
from clank_runtime.contracts.health import HealthPayload
from clank_runtime.version import ADAPTER_CONTRACT_VERSION

CLANK_ID = "smartwatch-clank"

#: Set to True ONLY after the real restored-DB schema has been observed and
#: mapped by someone with read access to the actual database.
LIVE_SCHEMA_VALIDATION = "BLOCKED"
LIVE_SCHEMA_VALIDATION_REASON = (
    "restored DB exists but its table/column inventory has not been "
    "observed by the adapter author; no schema names are invented")


class SmartwatchClankAdapter:
    def __init__(
        self,
        *,
        db_path: Path | str,
        clank_version: str = "0.0.0+unmapped-schema",
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
            description=(
                "Connected-wearable collector; observer coverage at "
                "schema-introspection stage (live semantic mapping blocked)"),
        )

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_identity=True,
            supports_status=True,       # existence/recency-level only
            supports_health=False,      # BLOCKED: no observed source tables
            supports_last_run=False,    # BLOCKED: run-table names unobserved
            supports_telemetry=True,    # introspection inventory only
            supports_delivery_accounting=False,
            supports_version=True,
            supports_manual_run=False,
            supports_local_fallback=False,
        )

    # -- honest status ----------------------------------------------------

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
        con = open_readonly(self.db_path)
        assert con is not None
        try:
            n_tables = con.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
            ).fetchone()[0]
        except sqlite3.Error:
            n_tables = 0
        finally:
            con.close()
        # A readable DB with tables proves the STORE exists - nothing about
        # collector behaviour. That claim belongs to the run plane once the
        # schema is mapped.
        return AdapterStatus(
            clank_id=CLANK_ID,
            operational_state=OperationalState.UNKNOWN,
            message=(f"store present ({n_tables} tables); operational state "
                     f"UNKNOWN until live schema mapping "
                     f"({LIVE_SCHEMA_VALIDATION})"),
            is_stale=False,
            observed_at=now,
        )

    def health(self) -> HealthPayload:
        now = datetime.now(UTC)
        exists = self.db_path.exists()
        return HealthPayload(
            clank_id=CLANK_ID,
            overall_status=OperationalState.UNKNOWN,
            warnings=[] if exists else [f"database missing: {self.db_path}"],
            is_stale_cache=not exists,
            observed_at=now,
        )

    def last_run(self) -> dict[str, Any]:
        """BLOCKED: run-table names have not been observed; never guessed."""
        return {
            "supported": False,
            "reason": f"live schema validation {LIVE_SCHEMA_VALIDATION}: "
                      f"{LIVE_SCHEMA_VALIDATION_REASON}",
            "finished_at": None,
            "status": None,
            "run_kind": None,
        }

    def schema_revision(self) -> int | str | None:
        con = open_readonly(self.db_path)
        if con is None:
            return None
        try:
            if not table_exists(con, "schema_migrations"):
                return None
            row = con.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
            return row[0] if row else None
        except sqlite3.Error:
            return None
        finally:
            con.close()

    # -- introspection inventory (the only proven evidence) ---------------

    def store_inventory(self) -> dict[str, Any]:
        """Table names + approximate row counts, strictly from sqlite
        metadata and counted reads. This is the substrate the future live
        schema mapping will be written against."""
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
