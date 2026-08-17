"""Attachment storage -- content-hashed, never executed, quarantines invalid input.

Attachments live on disk under two directories (both under Application
Support in the packaged app, never inside the repo/bundle):
  evidence_dir/<sha256>          -- accepted, content-addressed, immutable
  quarantine_dir/<uuid>-<name>   -- rejected input, kept for inspection

A file is quarantined rather than silently dropped or allowed to damage
canonical state when it: exceeds the size cap, has an empty/unreadable
body, or the caller-declared association (incident/output id) doesn't
exist. Quarantined files are never linked into canonical records and are
never executed or opened as anything but bytes.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024  # 25 MiB -- small evidence files only, per spec


class AttachmentQuarantined(Exception):
    def __init__(self, reason: str, quarantine_path: Path | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.quarantine_path = quarantine_path


class Attachment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attachment_id: str = Field(default_factory=lambda: str(uuid4()))
    incident_id: str | None = None
    output_id: str | None = None
    original_filename: str
    content_hash: str
    size_bytes: int
    stored_path: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


SCHEMA = """
CREATE TABLE IF NOT EXISTS attachments (
    attachment_id TEXT PRIMARY KEY, incident_id TEXT, output_id TEXT,
    original_filename TEXT NOT NULL, content_hash TEXT NOT NULL, size_bytes INTEGER NOT NULL,
    stored_path TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attach_incident ON attachments(incident_id);
CREATE INDEX IF NOT EXISTS idx_attach_output ON attachments(output_id);
CREATE INDEX IF NOT EXISTS idx_attach_hash ON attachments(content_hash);
"""


class AttachmentStore:
    def __init__(self, db_path: Path | str, evidence_dir: Path | str, quarantine_dir: Path | str) -> None:
        self.db_path = Path(db_path)
        self.evidence_dir = Path(evidence_dir)
        self.quarantine_dir = Path(quarantine_dir)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(self.db_path, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._con.execute("PRAGMA journal_mode=WAL")
        self._con.execute("PRAGMA busy_timeout=5000")
        self._con.executescript(SCHEMA)
        self._con.commit()

    def close(self) -> None:
        self._con.close()

    def _quarantine(self, content: bytes, filename: str, reason: str) -> AttachmentQuarantined:
        safe_name = "".join(c for c in filename if c.isalnum() or c in "._-") or "unnamed"
        path = self.quarantine_dir / f"{uuid4()}-{safe_name}"
        try:
            path.write_bytes(content)
        except OSError:
            path = None  # quarantine write itself failed -- still report the original reason
        return AttachmentQuarantined(reason, path)

    def save(self, *, content: bytes, original_filename: str,
             incident_id: str | None = None, output_id: str | None = None) -> Attachment:
        if not content:
            raise self._quarantine(content, original_filename, "empty_file")
        if len(content) > MAX_ATTACHMENT_BYTES:
            raise self._quarantine(content, original_filename, "exceeds_size_cap")
        content_hash = hashlib.sha256(content).hexdigest()
        existing = self._con.execute(
            "SELECT * FROM attachments WHERE content_hash=? AND "
            "(incident_id IS ? OR incident_id=?) AND (output_id IS ? OR output_id=?)",
            (content_hash, incident_id, incident_id, output_id, output_id),
        ).fetchone()
        if existing:
            return self._row(existing)
        stored_path = self.evidence_dir / content_hash
        if not stored_path.exists():
            stored_path.write_bytes(content)
        att = Attachment(
            incident_id=incident_id, output_id=output_id, original_filename=original_filename,
            content_hash=content_hash, size_bytes=len(content), stored_path=str(stored_path),
        )
        self._con.execute(
            "INSERT INTO attachments (attachment_id,incident_id,output_id,original_filename,"
            "content_hash,size_bytes,stored_path,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (att.attachment_id, att.incident_id, att.output_id, att.original_filename,
             att.content_hash, att.size_bytes, att.stored_path, att.created_at.isoformat()),
        )
        self._con.commit()
        return att

    def get(self, attachment_id: str) -> Attachment | None:
        row = self._con.execute("SELECT * FROM attachments WHERE attachment_id=?", (attachment_id,)).fetchone()
        return self._row(row) if row else None

    def for_incident(self, incident_id: str) -> list[Attachment]:
        rows = self._con.execute(
            "SELECT * FROM attachments WHERE incident_id=? ORDER BY created_at ASC", (incident_id,)
        ).fetchall()
        return [self._row(r) for r in rows]

    def for_output(self, output_id: str) -> list[Attachment]:
        rows = self._con.execute(
            "SELECT * FROM attachments WHERE output_id=? ORDER BY created_at ASC", (output_id,)
        ).fetchall()
        return [self._row(r) for r in rows]

    def read_bytes(self, attachment_id: str) -> bytes:
        att = self.get(attachment_id)
        if att is None:
            raise KeyError(f"unknown_attachment: {attachment_id}")
        return Path(att.stored_path).read_bytes()

    def _row(self, row: sqlite3.Row) -> Attachment:
        return Attachment(
            attachment_id=row["attachment_id"], incident_id=row["incident_id"], output_id=row["output_id"],
            original_filename=row["original_filename"], content_hash=row["content_hash"],
            size_bytes=row["size_bytes"], stored_path=row["stored_path"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
