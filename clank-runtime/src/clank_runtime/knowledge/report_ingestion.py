"""Deterministic, provenance-preserving report ingestion.

This is a data pipeline, not an LLM summarizer. Raw bytes are content-addressed
and immutable; chunks, claims, findings, and lessons are derived candidates
that can be reprocessed without replacing earlier revisions.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from clank_runtime.registry.core import ClankRegistry

MAX_CHUNK_BYTES = 64 * 1024
L_HEADER = re.compile(r"(?m)^-{10,}\n(?P<header>L-[A-Z0-9-]+\s+[—-]\s+.+)$")
ID_RE = re.compile(r"\bL-[A-Z0-9-]+\b")
SHA_RE = re.compile(r"\b[a-f0-9]{7,40}\b", re.I)
URL_RE = re.compile(r"https?://[^\s)>]+")

SCHEMA = """
CREATE TABLE IF NOT EXISTS report_ingestions (
 report_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, source_agent TEXT NOT NULL,
 source_type TEXT NOT NULL, filename TEXT, mime_type TEXT, byte_size INTEGER NOT NULL,
 text_size INTEGER NOT NULL, sha256 TEXT NOT NULL UNIQUE, raw_storage_path TEXT NOT NULL,
 ingestion_status TEXT NOT NULL, primary_clank_id TEXT, related_clank_ids_json TEXT NOT NULL,
 source_context TEXT, operator_note TEXT, report_types_json TEXT NOT NULL,
 processing_revision INTEGER NOT NULL DEFAULT 0, warnings_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS report_chunks (
 chunk_id TEXT PRIMARY KEY, report_id TEXT NOT NULL, revision INTEGER NOT NULL,
 ordinal INTEGER NOT NULL, start_offset INTEGER NOT NULL, end_offset INTEGER NOT NULL,
 heading_path TEXT, text TEXT NOT NULL, sha256 TEXT NOT NULL, classification TEXT,
 processing_status TEXT NOT NULL, error TEXT, UNIQUE(report_id, revision, ordinal)
);
CREATE TABLE IF NOT EXISTS report_claims (
 claim_id TEXT PRIMARY KEY, report_id TEXT NOT NULL, chunk_id TEXT NOT NULL,
 revision INTEGER NOT NULL, start_offset INTEGER, end_offset INTEGER, claim_text TEXT NOT NULL,
 claim_type TEXT NOT NULL, subject_clank_id TEXT, epistemic_status TEXT NOT NULL,
 supporting_evidence_refs_json TEXT NOT NULL, contradicting_evidence_refs_json TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS report_findings (
 finding_id TEXT PRIMARY KEY, report_id TEXT NOT NULL, revision INTEGER NOT NULL,
 source_chunk_ids_json TEXT NOT NULL, historical_incident_id TEXT, primary_clank_id TEXT,
 related_clank_ids_json TEXT NOT NULL, title TEXT NOT NULL, summary TEXT,
 epistemic_status TEXT NOT NULL, resolution_status TEXT NOT NULL, finding_type TEXT NOT NULL,
 failure_class TEXT, first_failed_gate TEXT, root_cause TEXT, fix_summary TEXT,
 lesson TEXT, responsibility_json TEXT NOT NULL, missing_evidence_json TEXT NOT NULL,
 supporting_claim_ids_json TEXT NOT NULL, review_status TEXT NOT NULL,
 UNIQUE(report_id, revision, finding_id)
);
CREATE TABLE IF NOT EXISTS report_lessons (
 lesson_id TEXT PRIMARY KEY, report_id TEXT NOT NULL, revision INTEGER NOT NULL,
 chunk_id TEXT NOT NULL, text TEXT NOT NULL, status TEXT NOT NULL,
 source_incident_refs_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_report_chunks_report ON report_chunks(report_id, revision, ordinal);
CREATE INDEX IF NOT EXISTS idx_report_findings_report ON report_findings(report_id, revision);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


class ReportIngestionStore:
    """SQLite metadata + filesystem raw archive for large report processing."""

    def __init__(self, db_path: Path | str, raw_dir: Path | str, registry: ClankRegistry) -> None:
        self.db_path = Path(db_path)
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.registry = registry
        self.con = sqlite3.connect(self.db_path, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA busy_timeout=5000")
        self.con.executescript(SCHEMA)
        self.con.commit()

    def close(self) -> None:
        self.con.close()

    def ingest_stream(
        self,
        stream: BinaryIO,
        *,
        source_agent: str,
        source_type: str = "text",
        filename: str | None = None,
        mime_type: str | None = None,
        primary_clank_id: str | None = None,
        related_clank_ids: list[str] | None = None,
        source_context: str | None = None,
        operator_note: str | None = None,
    ) -> dict:
        """Store bytes incrementally, then process a complete immutable report."""
        temp = self.raw_dir / f".upload-{uuid4()}"
        digest = hashlib.sha256()
        size = 0
        try:
            with temp.open("wb") as out:
                while True:
                    block = stream.read(1024 * 1024)
                    if not block:
                        break
                    digest.update(block)
                    size += len(block)
                    out.write(block)
            sha256 = digest.hexdigest()
            existing = self.con.execute(
                "SELECT report_id FROM report_ingestions WHERE sha256=?", (sha256,)
            ).fetchone()
            if existing:
                temp.unlink(missing_ok=True)
                return {
                    "report_id": existing["report_id"],
                    "status": "duplicate",
                    "duplicate_of": existing["report_id"],
                    "sha256": sha256,
                }
            raw_path = self.raw_dir / sha256
            temp.replace(raw_path)
            report_id = str(uuid4())
            related = related_clank_ids or []
            self.con.execute(
                "INSERT INTO report_ingestions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    report_id,
                    _now(),
                    source_agent,
                    source_type,
                    filename,
                    mime_type,
                    size,
                    0,
                    sha256,
                    str(raw_path),
                    "RAW_STORED",
                    primary_clank_id,
                    _json(related),
                    source_context,
                    operator_note,
                    _json([self._classify(filename, raw_path)]),
                    0,
                    "[]",
                ),
            )
            self.con.commit()
            result = self.process(report_id)
            result.update(
                {"report_id": report_id, "sha256": sha256, "byte_size": size, "status": "complete"}
            )
            return result
        except Exception:
            temp.unlink(missing_ok=True)
            raise

    def ingest_bytes(self, data: bytes, **kwargs) -> dict:
        from io import BytesIO

        return self.ingest_stream(BytesIO(data), **kwargs)

    def process(self, report_id: str, *, revision: int | None = None) -> dict:
        row = self.get(report_id)
        if row is None:
            raise KeyError(f"unknown_report: {report_id}")
        current = int(row["processing_revision"])
        rev = revision or current + 1
        text = Path(row["raw_storage_path"]).read_text(encoding="utf-8", errors="replace")
        chunks = list(self._chunks(report_id, text))
        for chunk in chunks:
            self.con.execute(
                "INSERT INTO report_chunks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (chunk[0], chunk[1], rev, *chunk[2:]),
            )
        findings = self._findings(report_id, text, rev, chunks)
        for f in findings:
            self.con.execute(
                "INSERT INTO report_findings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", f
            )
        for chunk in chunks:
            for lesson in self._lessons(report_id, chunk, rev):
                self.con.execute("INSERT INTO report_lessons VALUES (?,?,?,?,?,?,?)", lesson)
        claims = self._claims(report_id, rev, chunks)
        for claim in claims:
            self.con.execute("INSERT INTO report_claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", claim)
        self.con.execute(
            "UPDATE report_ingestions SET text_size=?, ingestion_status='COMPLETE', "
            "processing_revision=?, "
            "warnings_json=? WHERE report_id=?",
            (len(text), rev, _json([]), report_id),
        )
        self.con.commit()
        return {
            "processing_revision": rev,
            "chunks_total": len(chunks),
            "findings": len(findings),
            "claims": len(claims),
        }

    def get(self, report_id: str):
        return self.con.execute(
            "SELECT * FROM report_ingestions WHERE report_id=?", (report_id,)
        ).fetchone()

    def list_reports(self, limit: int = 100) -> list[dict]:
        return [
            dict(r)
            for r in self.con.execute(
                "SELECT * FROM report_ingestions ORDER BY created_at DESC LIMIT ?", (limit,)
            )
        ]

    def rows(self, table: str, report_id: str, revision: int | None = None) -> list[dict]:
        if table not in {"report_chunks", "report_claims", "report_findings", "report_lessons"}:
            raise ValueError("unsupported_report_table")
        query = f"SELECT * FROM {table} WHERE report_id=?"
        args: list[object] = [report_id]
        if revision is not None:
            query += " AND revision=?"
            args.append(revision)
        query += " ORDER BY rowid"
        return [dict(r) for r in self.con.execute(query, args)]

    def _classify(self, filename: str | None, path: Path) -> str:
        sample = filename or path.name
        low = sample.lower()
        if "historical" in low or "register" in low:
            return "HISTORICAL_REGISTER"
        return "UNKNOWN"

    def _chunks(self, report_id: str, text: str) -> Iterable[tuple]:
        matches = list(L_HEADER.finditer(text))
        spans = [
            (
                m.start(),
                matches[i + 1].start() if i + 1 < len(matches) else len(text),
                m.group("header"),
            )
            for i, m in enumerate(matches)
        ]
        if not spans:
            spans = [(0, len(text), None)]
        ordinal = 0
        for start, end, heading in spans:
            for offset in range(start, end, MAX_CHUNK_BYTES):
                stop = min(offset + MAX_CHUNK_BYTES, end)
                body = text[offset:stop]
                yield (
                    str(uuid4()),
                    report_id,
                    ordinal,
                    offset,
                    stop,
                    heading,
                    body,
                    _sha(body.encode()),
                    "HISTORICAL_REGISTER" if heading else "UNKNOWN",
                    "COMPLETE",
                    None,
                )
                ordinal += 1

    def _epistemic(self, block: str) -> str:
        for label in (
            "CANDIDATE / PROVENANCE REQUIRED",
            "PARTIALLY_CONFIRMED",
            "CONFIRMED",
            "RISK / NEAR-MISS",
            "BY DESIGN",
            "EXTERNAL",
            "UNKNOWN",
        ):
            if label in block:
                return label
        return "UNKNOWN"

    def _findings(self, report_id: str, text: str, rev: int, chunks: list[tuple]) -> list[tuple]:
        out = []
        for match in L_HEADER.finditer(text):
            end = next((m.start() for m in L_HEADER.finditer(text, match.end())), len(text))
            block = text[match.start() : end]
            incident_id, title = (
                match.group("header").split("—", 1)
                if "—" in match.group("header")
                else match.group("header").split("-", 1)
            )
            incident_id = incident_id.strip()
            title = title.strip()
            source_chunks = [c[0] for c in chunks if c[4] > match.start() and c[3] < end]
            section = self._section_context(text, match.start())
            primary = self._map_clank(f"{section}\n{block}")
            status = self._resolution(block)
            failure = next(
                (
                    x
                    for x in (
                        "SOURCE_GAP",
                        "REGION_GAP",
                        "DELIVERY_FAILURE",
                        "IDENTITY_ERROR",
                        "PARSER_FAILURE",
                        "BASELINE_FAILURE",
                    )
                    if x in block
                ),
                None,
            )
            root = self._field(block, "ROOT CAUSE")
            lesson = self._field(block, "LESSON")
            out.append(
                (
                    f"{report_id}:{rev}:{incident_id}",
                    report_id,
                    rev,
                    _json(source_chunks),
                    incident_id,
                    primary,
                    _json([]),
                    title,
                    block[:500],
                    self._epistemic(block),
                    status,
                    self._finding_type(block, failure),
                    failure,
                    None,
                    root,
                    self._field(block, "WHAT WAS DONE"),
                    lesson,
                    _json(self._responsibility(block)),
                    _json([]),
                    _json([]),
                    "AUTO_EXTRACTED",
                )
            )
        return out

    def _map_clank(self, block: str) -> str:
        low = block.lower()
        normalized = re.sub(r"[^a-z0-9]+", " ", low)
        for registration in self.registry.list_all():
            for candidate in (registration.clank_id, registration.display_name or ""):
                alias = re.sub(r"[^a-z0-9]+", " ", candidate.lower()).strip()
                if alias and re.search(rf"\b{re.escape(alias)}\b", normalized):
                    return registration.clank_id
        return "UNKNOWN"

    def _section_context(self, text: str, offset: int) -> str:
        sections = list(re.finditer(r"(?m)^# SECTION [A-Z] — .+$", text[:offset]))
        return sections[-1].group(0) if sections else ""

    def _resolution(self, block: str) -> str:
        upper = (self._field(block, "STATUS") or block[:400]).upper()
        if "UNFIXABLE_EXTERNAL" in upper or "NOT DIRECTLY FIXABLE" in upper:
            return "UNFIXABLE_EXTERNAL"
        normalized = re.sub(r"[^A-Z]+", "_", upper)
        for value in ("PARTIALLY_FIXED", "FIXED", "ONGOING", "OPEN", "BY_DESIGN", "SUPERSEDED"):
            if value in normalized:
                return value
        return "UNKNOWN"

    def _finding_type(self, block: str, failure: str | None) -> str:
        upper = block.upper()
        if "BY DESIGN" in upper or "BY_DESIGN" in upper:
            return "BY_DESIGN"
        if "RISK /" in upper or "NEAR-MISS" in upper:
            return "ARCHITECTURE_RISK"
        if "SOURCE / EXTERNAL" in upper or "EXTERNAL / NOT DIRECTLY FIXABLE" in upper:
            return "EXTERNAL_DEPENDENCY_FAILURE"
        if any(agent in upper for agent in ("CHATGPT", "CLAUDE", "CODEX", "GROK", "GEMINI")):
            return "AGENT_JUDGEMENT_FAILURE"
        return failure or "INCIDENT"

    def _responsibility(self, block: str) -> list[str]:
        upper = (self._field(block, "BLAME / CONTRIBUTION") or "").upper()
        labels = (
            "CLANK",
            "ARCHITECTURE",
            "SOURCE / EXTERNAL",
            "USER / OPERATOR",
            "CHATGPT",
            "CLAUDE",
            "CODEX",
            "GROK",
            "GEMINI",
            "SHARED",
            "UNKNOWN",
        )
        return [label for label in labels if label in upper]

    def _field(self, block: str, name: str) -> str | None:
        match = re.search(
            rf"(?ms)^{re.escape(name)}:\s*\n(.+?)(?=\n[A-Z][A-Z /_-]+:\s*|\n-{{10,}}|\Z)", block
        )
        return match.group(1).strip() if match else None

    def _claims(self, report_id: str, rev: int, chunks: list[tuple]) -> list[tuple]:
        out = []
        for chunk in chunks:
            text = chunk[6]
            for match in (
                list(ID_RE.finditer(text))
                + list(URL_RE.finditer(text))
                + list(SHA_RE.finditer(text))
            ):
                value = match.group(0)
                out.append(
                    (
                        str(uuid4()),
                        report_id,
                        chunk[0],
                        rev,
                        chunk[3] + match.start(),
                        chunk[3] + match.end(),
                        value,
                        "IDENTIFIER" if value.startswith("L-") else "REFERENCE",
                        None,
                        "REPORTED",
                        _json([]),
                        _json([]),
                        _now(),
                    )
                )
        return out

    def _lessons(self, report_id: str, chunk: tuple, rev: int) -> Iterable[tuple]:
        for match in re.finditer(
            r"(?ms)^LESSON:\s*\n(.+?)(?=\n[A-Z][A-Z /_-]+:\s*\n|\n-{10,}|\Z)", chunk[6]
        ):
            yield (
                str(uuid4()),
                report_id,
                rev,
                chunk[0],
                match.group(1).strip(),
                "REPORTED",
                _json(ID_RE.findall(match.group(1))),
            )
