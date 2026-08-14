"""Desktop local cache schema — separate from production Clank databases.

Corrupt desktop cache must never corrupt the production Fleet.
This module defines models and SQL DDL only; no production writes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from clank_runtime.version import CACHE_SCHEMA_VERSION

# SQL DDL for a replaceable local SQLite cache. One-writer desktop process.
DESKTOP_CACHE_DDL = """
CREATE TABLE IF NOT EXISTS cache_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fleet_snapshot (
    clank_id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    is_stale INTEGER NOT NULL DEFAULT 1,
    source TEXT NOT NULL DEFAULT 'cache'
);

CREATE TABLE IF NOT EXISTS source_health_cache (
    clank_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    is_stale INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (clank_id, source_id)
);

CREATE TABLE IF NOT EXISTS incident_cache (
    incident_id TEXT PRIMARY KEY,
    clank_id TEXT,
    payload_json TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    is_stale INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS telemetry_summary_cache (
    run_id TEXT PRIMARY KEY,
    clank_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    is_stale INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS offline_queue (
    queue_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    safety_class TEXT NOT NULL,
    action_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    clank_id TEXT,
    requires_reconfirmation INTEGER NOT NULL DEFAULT 0,
    auto_sync_eligible INTEGER NOT NULL DEFAULT 0,
    synced_at TEXT,
    discarded_reason TEXT
);

CREATE TABLE IF NOT EXISTS ledger_local (
    ledger_id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    originated_offline INTEGER NOT NULL DEFAULT 0,
    synced_at TEXT
);

CREATE TABLE IF NOT EXISTS hq_connection_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event TEXT NOT NULL,
    at TEXT NOT NULL,
    detail TEXT
);

CREATE TABLE IF NOT EXISTS machine_capability_cache (
    machine_id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    verified_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ui_preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class CacheMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default=CACHE_SCHEMA_VERSION)
    machine_id: str | None = None
    last_hq_contact_at: datetime | None = None
    hq_reachable: bool = False


class CachedFleetRow(BaseModel):
    """One Clank row in the local fleet snapshot."""

    model_config = ConfigDict(extra="forbid")

    clank_id: str
    payload: dict[str, Any]
    observed_at: datetime
    is_stale: bool = True
    source: str = "cache"
