"""Application-consistent backup/restore for the local Diagnostic knowledge
state -- SQLite DB via the online backup API (safe against a live,
concurrently-written WAL-mode DB), plus the content-addressed evidence /
attachments / quarantine directories.

Never copies the live .db file byte-for-byte while the app may be writing
to it -- sqlite3.Connection.backup() takes a consistent snapshot using
SQLite's own backup mechanism instead. The backup DB is checkpointed and
collapsed to a single self-contained file (no -wal/-shm sidecars) so it is
trivially portable.

Restore always writes into a destination the caller chose -- this module
never touches the live/default state root implicitly.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from diagnostic_clank.paths import StatePaths

MANIFEST_NAME = "MANIFEST.json"


@dataclass
class BackupManifest:
    backup_timestamp_utc: str
    source_repo_revision: str | None
    schema_version: str | None
    counts: dict[str, int]
    checksums: dict[str, str] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(
            {
                "backup_timestamp_utc": self.backup_timestamp_utc,
                "source_repo_revision": self.source_repo_revision,
                "schema_version": self.schema_version,
                "counts": self.counts,
                "checksums": self.checksums,
            },
            indent=2,
        )


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _copy_content_dir(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    if not src.is_dir():
        return
    for item in src.iterdir():
        if item.is_file():
            shutil.copy2(item, dest / item.name)


def create_backup(state: StatePaths, dest_dir: Path, *, source_repo_revision: str | None = None) -> BackupManifest:
    """Snapshot `state`'s DB + evidence/attachments/quarantine into `dest_dir`.

    Safe to call while the packaged app is running against `state`: uses
    SQLite's online backup API rather than copying the live file's bytes.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_db = dest_dir / "diagnostic.db"

    src_con = sqlite3.connect(state.db_path)
    src_con.execute("PRAGMA busy_timeout=5000")
    dest_con = sqlite3.connect(dest_db)
    try:
        src_con.backup(dest_con)
    finally:
        dest_con.close()
        src_con.close()

    # Collapse WAL to a single self-contained file.
    con = sqlite3.connect(dest_db)
    try:
        con.execute("PRAGMA wal_checkpoint(FULL)")
        con.execute("PRAGMA journal_mode=DELETE")
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"backup_integrity_check_failed: {integrity}")
        schema_version = con.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()
        counts = {
            table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("incidents", "incident_claims", "agent_outputs", "attachments")
        }
    finally:
        con.close()
    for sidecar in (dest_dir / "diagnostic.db-wal", dest_dir / "diagnostic.db-shm"):
        sidecar.unlink(missing_ok=True)

    _copy_content_dir(state.evidence_dir, dest_dir / "evidence")
    _copy_content_dir(state.attachments_dir, dest_dir / "attachments")
    _copy_content_dir(state.quarantine_dir, dest_dir / "quarantine")

    checksums = {"diagnostic.db": f"sha256:{_sha256_file(dest_db)}"}
    for sub in ("evidence", "attachments"):
        subdir = dest_dir / sub
        if subdir.is_dir():
            for item in sorted(subdir.iterdir()):
                if item.is_file():
                    checksums[f"{sub}/{item.name}"] = f"sha256:{_sha256_file(item)}"

    manifest = BackupManifest(
        backup_timestamp_utc=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        source_repo_revision=source_repo_revision,
        schema_version=str(schema_version[0]) if schema_version else None,
        counts=counts,
        checksums=checksums,
    )
    (dest_dir / MANIFEST_NAME).write_text(manifest.to_json(), encoding="utf-8")
    return manifest


def restore_backup(backup_dir: Path, dest_state_dir: Path) -> StatePaths:
    """Restore a backup produced by create_backup() into an isolated
    `dest_state_dir`. Never touches any other path -- the caller is
    responsible for choosing a destination that is not the live state root.
    """
    backup_db = backup_dir / "diagnostic.db"
    if not backup_db.is_file():
        raise FileNotFoundError(f"no diagnostic.db found under {backup_dir}")

    dest_state_dir.mkdir(parents=True, exist_ok=True)
    dest = StatePaths(
        home=dest_state_dir,
        db_path=dest_state_dir / "diagnostic.db",
        evidence_dir=dest_state_dir / "evidence",
        attachments_dir=dest_state_dir / "attachments",
        quarantine_dir=dest_state_dir / "quarantine",
        log_dir=dest_state_dir / "logs",
        runtime_dir=dest_state_dir / "runtime",
    )
    for d in (dest.evidence_dir, dest.attachments_dir, dest.quarantine_dir, dest.log_dir, dest.runtime_dir):
        d.mkdir(parents=True, exist_ok=True)

    shutil.copy2(backup_db, dest.db_path)
    _copy_content_dir(backup_dir / "evidence", dest.evidence_dir)
    _copy_content_dir(backup_dir / "attachments", dest.attachments_dir)
    _copy_content_dir(backup_dir / "quarantine", dest.quarantine_dir)

    con = sqlite3.connect(dest.db_path)
    try:
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"restored_db_integrity_check_failed: {integrity}")
    finally:
        con.close()

    return dest


def load_manifest(backup_dir: Path) -> BackupManifest | None:
    path = backup_dir / MANIFEST_NAME
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return BackupManifest(
        backup_timestamp_utc=data["backup_timestamp_utc"],
        source_repo_revision=data.get("source_repo_revision"),
        schema_version=data.get("schema_version"),
        counts=data.get("counts", {}),
        checksums=data.get("checksums", {}),
    )
