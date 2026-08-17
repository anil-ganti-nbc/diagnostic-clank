"""Incident / claim-history model -- Diagnostic Clank v0.1 Archivist scope.

Deliberately separate from clank_runtime.diagnostic.{models,engine}: those
implement the (unused by v0.1) deterministic autonomous diagnosis pipeline
(DiagnosticCase/DiagnosticResult/diagnose()), which v0.1 must not build on
top of. Incident here is a manual, owner-driven record meant to be fast to
fill out during real field testing -- not diagnosis-engine input. A future
version may correlate the two; v0.1 keeps them independent.

Foundation laws this module exists to uphold:
  CLAIM_RECORDED != CLAIM_TRUE
  LATEST_CLAIM != AUTHORITATIVE_TRUTH
  CONTRADICTION != CORRUPTION
A claim is never edited or deleted once recorded. Disputing or superseding
a claim changes its status field and links to the superseding claim; the
original text, source, and timestamp are permanent.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from clank_runtime.knowledge.inbox import ClaimVerification
from clank_runtime.registry.core import ClankRegistry


class IncidentStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    PARTIAL = "PARTIAL"
    DISPUTED = "DISPUTED"
    SUPERSEDED = "SUPERSEDED"


class IncidentClassification(StrEnum):
    """Section 9 seed vocabulary. Extensible: an incident may carry more
    than one (stored as a JSON list), and OTHER is always a safe fallback
    rather than forcing a bad fit."""
    MISS = "MISS"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    STALE_DISCOVERY = "STALE_DISCOVERY"
    DUPLICATE_ALERT = "DUPLICATE_ALERT"
    FALSE_REMOVAL = "FALSE_REMOVAL"
    IDENTITY_ERROR = "IDENTITY_ERROR"
    SOURCE_GAP = "SOURCE_GAP"
    REGION_GAP = "REGION_GAP"
    PARSER_FAILURE = "PARSER_FAILURE"
    SCHEDULER_FAILURE = "SCHEDULER_FAILURE"
    DELIVERY_FAILURE = "DELIVERY_FAILURE"
    NATIVE_CLIENT_FAILURE = "NATIVE_CLIENT_FAILURE"
    STATE_CORRUPTION = "STATE_CORRUPTION"
    PROVENANCE_FAILURE = "PROVENANCE_FAILURE"
    OPERATOR_UX_FAILURE = "OPERATOR_UX_FAILURE"
    ARCHITECTURE_FAILURE = "ARCHITECTURE_FAILURE"
    BASELINE_FAILURE = "BASELINE_FAILURE"
    OTHER = "OTHER"


class RootCauseCertainty(StrEnum):
    """Distinguishes an unproven root cause from a confirmed one. Never
    force one of the non-UNKNOWN values merely because a root_cause string
    is present -- an owner's first guess is a HYPOTHESIS, not a fact."""
    UNKNOWN = "UNKNOWN"
    HYPOTHESIS = "HYPOTHESIS"
    REPORTED_CLAIM = "REPORTED_CLAIM"
    CONFIRMED_FACT = "CONFIRMED_FACT"


class Incident(BaseModel):
    model_config = ConfigDict(extra="forbid")
    incident_id: str = Field(default_factory=lambda: str(uuid4()))
    clank_id: str
    title: str
    classification: list[IncidentClassification] = Field(default_factory=list)
    severity: str | None = None
    status: IncidentStatus = IncidentStatus.OPEN
    reported_by: str | None = None
    raw_evidence_ids: list[str] = Field(default_factory=list)
    expected_behaviour: str | None = None
    observed_behaviour: str | None = None
    root_cause: str | None = None
    root_cause_certainty: RootCauseCertainty = RootCauseCertainty.UNKNOWN
    resolution: str | None = None
    lessons: str | None = None
    reference_url: str | None = None
    related_incident_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class IncidentClaim(BaseModel):
    """A single historical statement about an incident. Never mutated after
    creation except for `status` and `superseded_by` -- see module docstring."""
    model_config = ConfigDict(extra="forbid")
    claim_id: str = Field(default_factory=lambda: str(uuid4()))
    incident_id: str
    text: str
    source: str | None = None  # e.g. "owner", "claude", agent output_id
    status: ClaimVerification = ClaimVerification.REPORTED
    superseded_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY, clank_id TEXT NOT NULL, title TEXT NOT NULL,
    classification_json TEXT NOT NULL DEFAULT '[]', severity TEXT, status TEXT NOT NULL,
    reported_by TEXT, raw_evidence_ids_json TEXT NOT NULL DEFAULT '[]',
    expected_behaviour TEXT, observed_behaviour TEXT, root_cause TEXT,
    root_cause_certainty TEXT NOT NULL DEFAULT 'UNKNOWN', resolution TEXT, lessons TEXT,
    reference_url TEXT, related_incident_ids_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_incidents_clank ON incidents(clank_id);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
CREATE TABLE IF NOT EXISTS incident_claims (
    claim_id TEXT PRIMARY KEY, incident_id TEXT NOT NULL, text TEXT NOT NULL,
    source TEXT, status TEXT NOT NULL, superseded_by TEXT, created_at TEXT NOT NULL,
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
);
CREATE INDEX IF NOT EXISTS idx_claims_incident ON incident_claims(incident_id);
CREATE VIRTUAL TABLE IF NOT EXISTS incidents_fts USING fts5(
    incident_id UNINDEXED, title, expected_behaviour, observed_behaviour,
    root_cause, resolution, lessons, clank_id
);
"""


class IncidentStore:
    def __init__(self, db_path: Path | str, registry: ClankRegistry) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry = registry
        self._con = sqlite3.connect(self.db_path, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._con.execute("PRAGMA journal_mode=WAL")
        self._con.execute("PRAGMA busy_timeout=5000")
        self._con.executescript(SCHEMA)
        self._con.commit()

    def close(self) -> None:
        self._con.close()

    def create(self, *, clank_id: str, title: str, **fields: Any) -> Incident:
        if clank_id != "fleet-wide":
            self.registry.require(clank_id)
        inc = Incident(clank_id=clank_id, title=title, **fields)
        self._insert(inc)
        self._index_fts(inc)
        return inc

    def _insert(self, inc: Incident) -> None:
        self._con.execute(
            """INSERT INTO incidents (incident_id,clank_id,title,classification_json,severity,
               status,reported_by,raw_evidence_ids_json,expected_behaviour,observed_behaviour,
               root_cause,root_cause_certainty,resolution,lessons,reference_url,
               related_incident_ids_json,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                inc.incident_id, inc.clank_id, inc.title,
                json.dumps([c.value for c in inc.classification]), inc.severity,
                inc.status.value, inc.reported_by, json.dumps(inc.raw_evidence_ids),
                inc.expected_behaviour, inc.observed_behaviour, inc.root_cause,
                inc.root_cause_certainty.value, inc.resolution, inc.lessons, inc.reference_url,
                json.dumps(inc.related_incident_ids),
                inc.created_at.isoformat(), inc.updated_at.isoformat(),
            ),
        )
        self._con.commit()

    def _index_fts(self, inc: Incident) -> None:
        self._con.execute(
            """INSERT INTO incidents_fts (incident_id,title,expected_behaviour,observed_behaviour,
               root_cause,resolution,lessons,clank_id) VALUES (?,?,?,?,?,?,?,?)""",
            (inc.incident_id, inc.title, inc.expected_behaviour or "", inc.observed_behaviour or "",
             inc.root_cause or "", inc.resolution or "", inc.lessons or "", inc.clank_id),
        )
        self._con.commit()

    def get(self, incident_id: str) -> Incident | None:
        row = self._con.execute("SELECT * FROM incidents WHERE incident_id=?", (incident_id,)).fetchone()
        return self._row(row) if row else None

    def list(self, *, clank_id: str | None = None, status: str | None = None, limit: int = 200) -> list[Incident]:
        q, params = "SELECT * FROM incidents WHERE 1=1", []
        if clank_id:
            q += " AND clank_id=?"; params.append(clank_id)
        if status:
            q += " AND status=?"; params.append(status)
        q += " ORDER BY updated_at DESC LIMIT ?"; params.append(limit)
        return [self._row(r) for r in self._con.execute(q, params).fetchall()]

    def update_status(self, incident_id: str, status: IncidentStatus) -> Incident:
        """Status transitions are allowed (an incident's own workflow state
        legitimately changes); this is distinct from mutating a recorded
        claim's text, which is never permitted."""
        inc = self.get(incident_id)
        if inc is None:
            raise KeyError(f"unknown_incident: {incident_id}")
        now = datetime.now(UTC)
        self._con.execute(
            "UPDATE incidents SET status=?, updated_at=? WHERE incident_id=?",
            (status.value, now.isoformat(), incident_id),
        )
        self._con.commit()
        inc.status = status
        inc.updated_at = now
        return inc

    def link_evidence(self, incident_id: str, output_id: str) -> Incident:
        inc = self.get(incident_id)
        if inc is None:
            raise KeyError(f"unknown_incident: {incident_id}")
        if output_id not in inc.raw_evidence_ids:
            inc.raw_evidence_ids.append(output_id)
            self._con.execute(
                "UPDATE incidents SET raw_evidence_ids_json=?, updated_at=? WHERE incident_id=?",
                (json.dumps(inc.raw_evidence_ids), datetime.now(UTC).isoformat(), incident_id),
            )
            self._con.commit()
        return inc

    def relate(self, incident_id: str, related_incident_id: str) -> Incident:
        inc = self.get(incident_id)
        if inc is None:
            raise KeyError(f"unknown_incident: {incident_id}")
        if related_incident_id not in inc.related_incident_ids:
            inc.related_incident_ids.append(related_incident_id)
            self._con.execute(
                "UPDATE incidents SET related_incident_ids_json=?, updated_at=? WHERE incident_id=?",
                (json.dumps(inc.related_incident_ids), datetime.now(UTC).isoformat(), incident_id),
            )
            self._con.commit()
        return inc

    # -- claim history / contradictions -----------------------------------

    def add_claim(self, incident_id: str, text: str, *, source: str | None = None,
                  status: ClaimVerification = ClaimVerification.REPORTED) -> IncidentClaim:
        if self.get(incident_id) is None:
            raise KeyError(f"unknown_incident: {incident_id}")
        claim = IncidentClaim(incident_id=incident_id, text=text, source=source, status=status)
        self._con.execute(
            "INSERT INTO incident_claims (claim_id,incident_id,text,source,status,superseded_by,created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (claim.claim_id, claim.incident_id, claim.text, claim.source, claim.status.value,
             claim.superseded_by, claim.created_at.isoformat()),
        )
        self._con.commit()
        return claim

    def claims_for(self, incident_id: str) -> list[IncidentClaim]:
        rows = self._con.execute(
            "SELECT * FROM incident_claims WHERE incident_id=? ORDER BY created_at ASC", (incident_id,)
        ).fetchall()
        return [self._claim_row(r) for r in rows]

    def supersede_claim(self, old_claim_id: str, new_text: str, *, source: str | None = None,
                         status: ClaimVerification = ClaimVerification.REPORTED,
                         old_becomes: ClaimVerification = ClaimVerification.SUPERSEDED) -> tuple[IncidentClaim, IncidentClaim]:
        """Records a new claim and marks the old one superseded/disputed --
        both remain permanently queryable. Never deletes or rewrites the
        old claim's text."""
        row = self._con.execute("SELECT * FROM incident_claims WHERE claim_id=?", (old_claim_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown_claim: {old_claim_id}")
        old = self._claim_row(row)
        new = self.add_claim(old.incident_id, new_text, source=source, status=status)
        self._con.execute(
            "UPDATE incident_claims SET status=?, superseded_by=? WHERE claim_id=?",
            (old_becomes.value, new.claim_id, old_claim_id),
        )
        self._con.commit()
        old.status = old_becomes
        old.superseded_by = new.claim_id
        return old, new

    # -- search -------------------------------------------------------------

    def search(self, query: str, *, limit: int = 50) -> list[Incident]:
        if not query.strip():
            return []
        try:
            rows = self._con.execute(
                "SELECT incident_id FROM incidents_fts WHERE incidents_fts MATCH ? LIMIT ?",
                (query, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            # malformed FTS query syntax from raw user input -- fall back to
            # a plain LIKE scan rather than surfacing an error for a paste
            like = f"%{query}%"
            rows = self._con.execute(
                "SELECT incident_id FROM incidents WHERE title LIKE ? OR observed_behaviour LIKE ? "
                "OR root_cause LIKE ? OR resolution LIKE ? LIMIT ?",
                (like, like, like, like, limit),
            ).fetchall()
            return [self.get(r["incident_id"]) for r in rows if self.get(r["incident_id"])]
        return [inc for r in rows if (inc := self.get(r["incident_id"])) is not None]

    # -- row mapping ----------------------------------------------------------

    def _row(self, row: sqlite3.Row) -> Incident:
        return Incident(
            incident_id=row["incident_id"], clank_id=row["clank_id"], title=row["title"],
            classification=[IncidentClassification(c) for c in json.loads(row["classification_json"] or "[]")],
            severity=row["severity"], status=IncidentStatus(row["status"]), reported_by=row["reported_by"],
            raw_evidence_ids=json.loads(row["raw_evidence_ids_json"] or "[]"),
            expected_behaviour=row["expected_behaviour"], observed_behaviour=row["observed_behaviour"],
            root_cause=row["root_cause"], root_cause_certainty=RootCauseCertainty(row["root_cause_certainty"]),
            resolution=row["resolution"], lessons=row["lessons"], reference_url=row["reference_url"],
            related_incident_ids=json.loads(row["related_incident_ids_json"] or "[]"),
            created_at=datetime.fromisoformat(row["created_at"]), updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _claim_row(self, row: sqlite3.Row) -> IncidentClaim:
        return IncidentClaim(
            claim_id=row["claim_id"], incident_id=row["incident_id"], text=row["text"],
            source=row["source"], status=ClaimVerification(row["status"]),
            superseded_by=row["superseded_by"], created_at=datetime.fromisoformat(row["created_at"]),
        )
