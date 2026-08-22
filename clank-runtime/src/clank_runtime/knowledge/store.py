"""DiagnosticKnowledgeStore -- the single facade the v0.1 GUI talks to.

Composes AgentOutputInbox (raw evidence), IncidentStore (incidents/claims),
and AttachmentStore (files) against one shared SQLite file, plus a search
index over raw report text. This is the only entry point the GUI should
import from -- it does not expose a lower-authority path around the raw
evidence immutability / dedup / quarantine rules each sub-store enforces.

Re-indexing derived knowledge from preserved raw evidence is always
possible: reindex_reports() rebuilds the report search index purely from
the immutable agent_outputs table, never from anything else.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from clank_runtime.knowledge.attachments import Attachment, AttachmentQuarantined, AttachmentStore
from clank_runtime.knowledge.clankops_record import CLANKOPSRecord, extract_clankops_record
from clank_runtime.knowledge.inbox import AgentFamily, AgentOutputInbox, AgentOutputRecord, OutputType
from clank_runtime.knowledge.dispositions import (  # ADR-0003 §4/§5
    Disposition,
    DispositionRecord,
    RecommendationDispositionStore,
    SelfVerificationError,
    canonical_producer_identity,
    ensure_disposition_tables,
    transition_claim,
)
from clank_runtime.knowledge.incidents import (
    ClaimVerification,
    Incident,
    IncidentClaim,
    IncidentClassification,
    IncidentStatus,
    IncidentStore,
    RootCauseCertainty,
)
from clank_runtime.registry.core import ClankRegistration, ClankRegistry
from clank_runtime.knowledge.report_ingestion import ReportIngestionStore


@dataclass
class IngestResult:
    output: AgentOutputRecord
    clankops_record: CLANKOPSRecord
    was_duplicate: bool


class DiagnosticKnowledgeStore:
    def __init__(self, db_path: Path | str, evidence_dir: Path | str, quarantine_dir: Path | str,
                 registry: ClankRegistry | None = None) -> None:
        self.db_path = Path(db_path)
        self.registry = registry or ClankRegistry()
        self.inbox = AgentOutputInbox(self.db_path, self.registry)
        self.incidents = IncidentStore(self.db_path, self.registry)
        self.attachments = AttachmentStore(self.db_path, evidence_dir, quarantine_dir)
        self.reports = ReportIngestionStore(self.db_path, Path(evidence_dir) / "reports", self.registry)
        self._reports_con = sqlite3.connect(self.db_path, check_same_thread=False)
        self._reports_con.row_factory = sqlite3.Row
        # ADR-0003 §4: append-only operator dispositions over the same DB file
        ensure_disposition_tables(self._reports_con)
        self.dispositions = RecommendationDispositionStore(self.inbox)
        self._reports_con.executescript(
            "CREATE VIRTUAL TABLE IF NOT EXISTS reports_fts USING fts5("
            "output_id UNINDEXED, raw_text, agent_family, primary_clank_id, output_type)"
        )
        self._reports_con.commit()

    def close(self) -> None:
        self.inbox.close()
        self.incidents.close()
        self.attachments.close()
        self._reports_con.close()
        self.reports.close()

    # -- ingestion ------------------------------------------------------------

    def ingest_report(self, *, agent_family: AgentFamily, primary_clank_id: str, raw_text: str,
                       output_type: OutputType = OutputType.GENERAL_NOTE,
                       related_clank_ids: list[str] | None = None, misc_source: str | None = None,
                       session_label: str | None = None,
                       related_diagnostic_case_id: str | None = None) -> IngestResult:
        dup_marker: list[str] = []
        record = self.inbox.save(
            agent_family=agent_family, primary_clank_id=primary_clank_id, raw_text=raw_text,
            output_type=output_type, related_clank_ids=related_clank_ids, misc_source=misc_source,
            session_label=session_label, related_diagnostic_case_id=related_diagnostic_case_id,
            _duplicate_of=dup_marker,
        )
        was_duplicate = bool(dup_marker)
        if not was_duplicate:
            self._index_report(record)
        return IngestResult(
            output=record, clankops_record=extract_clankops_record(raw_text), was_duplicate=was_duplicate,
        )

    def _index_report(self, record: AgentOutputRecord) -> None:
        self._reports_con.execute(
            "INSERT INTO reports_fts (output_id,raw_text,agent_family,primary_clank_id,output_type) "
            "VALUES (?,?,?,?,?)",
            (record.output_id, record.raw_text, record.agent_family.value,
             record.primary_clank_id, record.output_type.value),
        )
        self._reports_con.commit()

    def reindex_reports(self) -> int:
        """Rebuilds the report search index purely from the immutable raw
        evidence table -- proves derived knowledge can always be
        reconstructed from preserved raw evidence alone."""
        self._reports_con.execute("DELETE FROM reports_fts")
        self._reports_con.commit()
        count = 0
        for record in self.inbox.list(limit=1_000_000):
            self._index_report(record)
            count += 1
        return count

    def search_reports(self, query: str, *, limit: int = 50) -> list[AgentOutputRecord]:
        if not query.strip():
            return []
        try:
            rows = self._reports_con.execute(
                "SELECT output_id FROM reports_fts WHERE reports_fts MATCH ? LIMIT ?", (query, limit)
            ).fetchall()
        except sqlite3.OperationalError:
            like = f"%{query}%"
            rows = self._reports_con.execute(
                "SELECT output_id FROM reports_fts WHERE raw_text LIKE ? LIMIT ?", (like, limit)
            ).fetchall()
        return [rec for r in rows if (rec := self.inbox.get(r["output_id"])) is not None]

    def search_all(self, query: str, *, limit: int = 50) -> dict[str, list]:
        return {
            "incidents": self.incidents.search(query, limit=limit),
            "reports": self.search_reports(query, limit=limit),
        }


__all__ = [
    "Attachment", "AttachmentQuarantined", "AttachmentStore",
    "AgentFamily", "AgentOutputInbox", "AgentOutputRecord", "OutputType",
    "CLANKOPSRecord", "extract_clankops_record",
    "ClaimVerification", "Incident", "IncidentClaim", "IncidentClassification",
    "IncidentStatus", "IncidentStore", "RootCauseCertainty",
    "ClankRegistration", "ClankRegistry",
    "DiagnosticKnowledgeStore", "IngestResult",
    "ReportIngestionStore",
]
