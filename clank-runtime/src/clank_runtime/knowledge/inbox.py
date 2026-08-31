"""Agent Output Inbox — immutable raw text; registry-backed clank_id."""
from __future__ import annotations
import hashlib, json, re, sqlite3
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field
from clank_runtime.registry.core import ClankRegistry

class AgentFamily(StrEnum):
    CLAUDE = "claude"; CODEX = "codex"; GROK = "grok"; MISC = "misc"

class OutputType(StrEnum):
    INVESTIGATION = "investigation"; BUILD_RESULT = "build_result"; TEST_RESULT = "test_result"
    AUDIT = "audit"; HANDOFF = "handoff"; RESEARCH = "research"; SOURCE_RESEARCH = "source_research"
    FIX_REPORT = "fix_report"; DEPLOYMENT_REPORT = "deployment_report"; SOAK_REPORT = "soak_report"
    FAILURE_REPORT = "failure_report"; GENERAL_NOTE = "general_note"
    RECOMMENDATION = "recommendation"  # ADR-0003 §2: Motherclank M3 advisory output

class ClaimVerification(StrEnum):
    REPORTED = "reported"; CORROBORATED = "corroborated"; VERIFIED = "verified"
    CONTRADICTED = "contradicted"; SUPERSEDED = "superseded"

def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

class AgentOutputRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    output_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    agent_family: AgentFamily
    agent_name: str | None = None
    primary_clank_id: str
    related_clank_ids: list[str] = Field(default_factory=list)
    output_type: OutputType = OutputType.GENERAL_NOTE
    session_label: str | None = None
    raw_text: str
    raw_text_hash: str
    related_diagnostic_case_id: str | None = None
    related_git_revision: str | None = None
    misc_source: str | None = None
    ingestion_status: str = "stored"
    # ADR-0003 §2: logical recommendation identity (Motherclank recommendation_id).
    # Content dedup (raw_text_hash) is NOT identity; changed content under one
    # external_ref forms an immutable version series.
    external_ref: str | None = None

class ExtractedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_id: str = Field(default_factory=lambda: str(uuid4()))
    output_id: str
    text: str
    status: ClaimVerification = ClaimVerification.REPORTED
    verification_source_output_id: str | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_outputs (
    output_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, agent_family TEXT NOT NULL,
    primary_clank_id TEXT NOT NULL, related_clank_ids_json TEXT NOT NULL DEFAULT '[]',
    output_type TEXT NOT NULL, raw_text TEXT NOT NULL, raw_text_hash TEXT NOT NULL,
    related_diagnostic_case_id TEXT, related_git_revision TEXT, misc_source TEXT, session_label TEXT
);
CREATE INDEX IF NOT EXISTS idx_ao_clank ON agent_outputs(primary_clank_id);
CREATE TABLE IF NOT EXISTS agent_claims (
    claim_id TEXT PRIMARY KEY, output_id TEXT NOT NULL, text TEXT NOT NULL,
    status TEXT NOT NULL, verification_source_output_id TEXT
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

# ADR-0003 §2: additive v1 -> v2 migration. Pre-existing rows read as
# external_ref = NULL. raw_text_hash semantics are untouched.
MIGRATIONS: dict[str, str] = {
    "2": "ALTER TABLE agent_outputs ADD COLUMN external_ref TEXT;",
}
_GIT_SHA40_RE = re.compile(
    r"(?<![0-9a-fA-F])(?<!sha256:)(?<!sha256=)([0-9a-fA-F]{40})(?![0-9a-fA-F])"
)


def extract_related_git_revision(raw_text: str) -> str | None:
    """Return a 40-char git SHA from raw_text, or None.

    Content hashes (`sha256:<hex>`, `sha256=<hex>`) and short hex fragments
    (`rec-<16 hex>`) must not be persisted as related_git_revision. Absence
    stays None (UNKNOWN), never a fabricated revision.
    """
    for match in _GIT_SHA40_RE.finditer(raw_text):
        start = match.start()
        prefix = raw_text[max(0, start - 7):start].lower()
        if prefix.endswith("sha256:") or prefix.endswith("sha256="):
            continue
        return match.group(1).lower()
    return None

class AgentOutputInbox:
    def __init__(self, db_path: Path | str, registry: ClankRegistry) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry = registry
        self._con = sqlite3.connect(self.db_path, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._con.executescript(SCHEMA)
        self._con.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('schema_version','1')")
        self._apply_migrations()
        self._con.commit()

    def _apply_migrations(self) -> None:
        """ADR-0003 §2: additive, forward-only schema migrations.

        A v1 database is migrated to v2 in place; a fresh database created
        from SCHEMA already carries every column, so migrations are applied
        idempotently by probing for the column's existence.
        """
        row = self._con.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()
        current = int(row["value"]) if row else 1
        for version in sorted(MIGRATIONS, key=int):
            if int(version) <= current:
                continue
            # Idempotence probe: skip if the migration's column already exists
            # (fresh DBs built from SCHEMA include it while meta still says 1).
            if "ADD COLUMN external_ref" in MIGRATIONS[version]:
                cols = {r[1] for r in self._con.execute("PRAGMA table_info(agent_outputs)")}
                if "external_ref" in cols:
                    self._con.execute(
                        "UPDATE meta SET value=? WHERE key='schema_version'", (version,)
                    )
                    continue
            self._con.executescript(MIGRATIONS[version])
            self._con.execute(
                "UPDATE meta SET value=? WHERE key='schema_version'", (version,)
            )

    def close(self) -> None:
        self._con.close()

    def find_by_hash(self, raw_text_hash: str) -> AgentOutputRecord | None:
        row = self._con.execute(
            "SELECT * FROM agent_outputs WHERE raw_text_hash=? ORDER BY created_at ASC LIMIT 1",
            (raw_text_hash,),
        ).fetchone()
        return self._row(row) if row else None

    def save(self, *, agent_family: AgentFamily, primary_clank_id: str, raw_text: str,
             output_type: OutputType = OutputType.GENERAL_NOTE,
             related_clank_ids: list[str] | None = None, misc_source: str | None = None,
             session_label: str | None = None, related_diagnostic_case_id: str | None = None,
             external_ref: str | None = None,
             _duplicate_of: list[str] | None = None) -> AgentOutputRecord:
        """Content-hash deduplicated: re-saving identical raw_text returns the
        existing canonical record instead of inserting a second copy. The
        duplicate attempt is still observable via _duplicate_of (an
        operational log list the caller may append to), never silently lost,
        but never becomes a second canonical evidence row either.

        ADR-0003 §2.1/§2.2: raw_text_hash dedup is CONTENT dedup only.
        Logical recommendation identity travels in external_ref; changed
        content under the same external_ref inserts a NEW immutable row
        (a version series), never an update."""
        if not raw_text.strip():
            raise ValueError("empty_output")
        existing = self.find_by_hash(text_hash(raw_text))
        if existing is not None:
            if _duplicate_of is not None:
                _duplicate_of.append(existing.output_id)
            return existing
        if primary_clank_id != "fleet-wide":
            self.registry.require(primary_clank_id)
        for rid in related_clank_ids or []:
            if rid != "fleet-wide":
                self.registry.require(rid)
        rec = AgentOutputRecord(
            agent_family=agent_family, primary_clank_id=primary_clank_id,
            related_clank_ids=list(related_clank_ids or []), output_type=output_type,
            raw_text=raw_text, raw_text_hash=text_hash(raw_text), misc_source=misc_source,
            session_label=session_label, related_diagnostic_case_id=related_diagnostic_case_id,
            external_ref=external_ref,
            related_git_revision=extract_related_git_revision(raw_text),
        )
        self._con.execute(
            """INSERT INTO agent_outputs (output_id,created_at,agent_family,primary_clank_id,
               related_clank_ids_json,output_type,raw_text,raw_text_hash,related_diagnostic_case_id,
               related_git_revision,misc_source,session_label,external_ref)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rec.output_id, rec.created_at.isoformat(), rec.agent_family.value, rec.primary_clank_id,
             json.dumps(rec.related_clank_ids), rec.output_type.value, rec.raw_text, rec.raw_text_hash,
             rec.related_diagnostic_case_id,
             rec.related_git_revision, rec.misc_source, rec.session_label, rec.external_ref),
        )
        self._con.commit()
        for line in raw_text.splitlines():
            if any(k in line.lower() for k in ("suspect", "failure", "ready")) and len(line.strip()) > 8:
                self._con.execute(
                    "INSERT INTO agent_claims (claim_id,output_id,text,status) VALUES (?,?,?,?)",
                    (str(uuid4()), rec.output_id, line.strip()[:500], ClaimVerification.REPORTED.value),
                )
                self._con.commit()
        return rec

    def get(self, output_id: str) -> AgentOutputRecord | None:
        row = self._con.execute("SELECT * FROM agent_outputs WHERE output_id=?", (output_id,)).fetchone()
        return self._row(row) if row else None

    def list(self, *, clank_id: str | None = None, agent_family: str | None = None, limit: int = 50) -> list[AgentOutputRecord]:
        q, params = "SELECT * FROM agent_outputs WHERE 1=1", []
        if clank_id:
            q += " AND primary_clank_id=?"; params.append(clank_id)
        if agent_family:
            q += " AND agent_family=?"; params.append(agent_family)
        q += " ORDER BY created_at DESC LIMIT ?"; params.append(limit)
        return [self._row(r) for r in self._con.execute(q, params).fetchall()]

    def claims_for(self, output_id: str) -> list[ExtractedClaim]:
        rows = self._con.execute("SELECT * FROM agent_claims WHERE output_id=?", (output_id,)).fetchall()
        return [ExtractedClaim(claim_id=r["claim_id"], output_id=r["output_id"], text=r["text"],
                               status=ClaimVerification(r["status"]),
                               verification_source_output_id=r["verification_source_output_id"]) for r in rows]

    def _row(self, row: sqlite3.Row) -> AgentOutputRecord:
        return AgentOutputRecord(
            output_id=row["output_id"], created_at=datetime.fromisoformat(row["created_at"]),
            agent_family=AgentFamily(row["agent_family"]), primary_clank_id=row["primary_clank_id"],
            related_clank_ids=json.loads(row["related_clank_ids_json"] or "[]"),
            output_type=OutputType(row["output_type"]), raw_text=row["raw_text"],
            raw_text_hash=row["raw_text_hash"], related_diagnostic_case_id=row["related_diagnostic_case_id"],
            related_git_revision=row["related_git_revision"], misc_source=row["misc_source"],
            session_label=row["session_label"],
            external_ref=row["external_ref"] if "external_ref" in row.keys() else None,
        )

    def latest_by_external_ref(self, external_ref: str) -> AgentOutputRecord | None:
        """ADR-0003 §2.2: canonical version = latest persisted record for the
        ref under the deterministic order (created_at, output_id). The Inbox
        has no monotonic insertion identity; created_at stays provenance
        metadata, this ordering is only a total order over persisted rows."""
        rows = self._con.execute(
            """SELECT * FROM agent_outputs WHERE external_ref=?
               ORDER BY created_at ASC, output_id ASC""",
            (external_ref,),
        ).fetchall()
        return self._row(rows[-1]) if rows else None

    def assert_raw_roundtrip(self, output_id: str, original: str) -> None:
        rec = self.get(output_id)
        assert rec is not None
        if rec.raw_text != original or rec.raw_text_hash != text_hash(original):
            raise RuntimeError("raw_text mutated")

    def schema_version(self) -> str:
        row = self._con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        return row["value"] if row else "0"
