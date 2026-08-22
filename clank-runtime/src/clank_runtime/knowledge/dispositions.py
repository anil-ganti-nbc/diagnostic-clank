"""ADR-0003 §4/§5 — recommendation dispositions and claim-verification transitions.

Two independent dimensions, per the reviewed contract:

1. VERIFICATION (existing claims model): ClaimVerification status on
   agent_claims rows, transitioned only through :meth:`AgentOutputInbox.transition_claim`,
   which enforces cross-producer verification via CANONICAL producer identity
   (AgentFamily + misc_source for MISC outputs), never AgentFamily alone.

2. DISPOSITION (new): operator-only ACT/DISMISS/DEFER records in a separate
   append-only table keyed by logical recommendation external_ref. Append-only
   is enforced AT THE DATABASE LEVEL by SQLite triggers rejecting UPDATE and
   DELETE; a revised decision inserts another row. Disposition never touches
   ClaimVerification, recommendation content rows, or IncidentStatus.
"""
from __future__ import annotations

import sqlite3
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from clank_runtime.knowledge.inbox import (
    AgentOutputInbox,
    ClaimVerification,
    text_hash,
)


class Disposition(StrEnum):
    ACT = "ACT"
    DISMISS = "DISMISS"
    DEFER = "DEFER"


class DispositionRecord(BaseModel):
    """One immutable operator decision. extra='forbid' keeps the shape closed."""
    model_config = ConfigDict(extra="forbid")
    disposition_id: str = Field(default_factory=lambda: str(uuid4()))
    external_ref: str
    disposition: Disposition
    decided_by: str
    decided_at: str  # ISO string supplied by caller; provenance metadata, not ordering
    note: str | None = None


class SelfVerificationError(ValueError):
    """A producer attempted to verify its own output."""


DISPOSITION_SCHEMA = """
CREATE TABLE IF NOT EXISTS recommendation_dispositions (
    disposition_id TEXT PRIMARY KEY,
    external_ref TEXT NOT NULL,
    disposition TEXT NOT NULL CHECK (disposition IN ('ACT','DISMISS','DEFER')),
    decided_by TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    note TEXT
);
CREATE INDEX IF NOT EXISTS idx_disp_ref ON recommendation_dispositions(external_ref);
"""

_APPEND_ONLY_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS trg_dispositions_no_update
BEFORE UPDATE ON recommendation_dispositions
BEGIN
    SELECT RAISE(ABORT, 'recommendation_dispositions is append-only: UPDATE rejected');
END;
CREATE TRIGGER IF NOT EXISTS trg_dispositions_no_delete
BEFORE DELETE ON recommendation_dispositions
BEGIN
    SELECT RAISE(ABORT, 'recommendation_dispositions is append-only: DELETE rejected');
END;
"""


def ensure_disposition_tables(con: sqlite3.Connection) -> None:
    con.executescript(DISPOSITION_SCHEMA)
    con.executescript(_APPEND_ONLY_TRIGGERS)
    con.commit()


def canonical_producer_identity(record: Any) -> tuple[str, ...]:
    """ADR-0003 §5 binding clarification: producer identity is canonical, not
    AgentFamily alone. For MISC outputs the misc_source participates, so two
    MISC producers with different misc_source values are DIFFERENT producers.
    Normal agent outputs are identified by family (+ optional agent_name)."""
    family = record.agent_family.value if hasattr(record.agent_family, "value") else str(record.agent_family)
    if family == "MISC" or family == "misc":
        return ("misc", getattr(record, "misc_source", None) or "")
    name = getattr(record, "agent_name", None)
    return (family, name) if name else (family,)


def _producer_of_output(inbox: AgentOutputInbox, output_id: str) -> tuple[str, ...]:
    rec = inbox.get(output_id)
    if rec is None:
        raise KeyError(f"unknown_output: {output_id}")
    return canonical_producer_identity(rec)


class RecommendationDispositionStore:
    """Append-only operator disposition history for recommendations.

    Composes over the same SQLite database as the Inbox (one file, separate
    tables); it writes ONLY its own table. Database-level triggers reject any
    UPDATE or DELETE, so append-only is a storage property, not an API
    convention."""

    def __init__(self, inbox: AgentOutputInbox) -> None:
        self._inbox = inbox
        ensure_disposition_tables(inbox._con)

    def record(self, *, external_ref: str, disposition: Disposition | str,
               decided_by: str, decided_at: str, note: str | None = None) -> DispositionRecord:
        disp = Disposition(disposition) if isinstance(disposition, str) else disposition
        rec = DispositionRecord(
            external_ref=external_ref, disposition=disp,
            decided_by=decided_by, decided_at=decided_at, note=note,
        )
        self._inbox._con.execute(
            """INSERT INTO recommendation_dispositions
               (disposition_id, external_ref, disposition, decided_by, decided_at, note)
               VALUES (?,?,?,?,?,?)""",
            (rec.disposition_id, rec.external_ref, rec.disposition.value,
             rec.decided_by, rec.decided_at, rec.note),
        )
        self._inbox._con.commit()
        return rec

    def history(self, external_ref: str) -> list[DispositionRecord]:
        rows = self._inbox._con.execute(
            """SELECT * FROM recommendation_dispositions WHERE external_ref=?
               ORDER BY decided_at ASC, disposition_id ASC""",
            (external_ref,),
        ).fetchall()
        return [DispositionRecord(
            disposition_id=r["disposition_id"], external_ref=r["external_ref"],
            disposition=Disposition(r["disposition"]), decided_by=r["decided_by"],
            decided_at=r["decided_at"], note=r["note"],
        ) for r in rows]

    def latest(self, external_ref: str) -> DispositionRecord | None:
        hist = self.history(external_ref)
        return hist[-1] if hist else None


def transition_claim(inbox: AgentOutputInbox, *, claim_id: str,
                     status: ClaimVerification | str,
                     verification_source_output_id: str) -> dict[str, str]:
    """Transition one claim's verification status.

    Fail-closed rules:
    - unknown claim -> KeyError;
    - unknown/nonexistent verification source output -> KeyError (never silent);
    - self-verification (same canonical producer identity between the claim's
      parent output and the cited source output) -> SelfVerificationError.

    The source output id is persisted on the claim row either way it is
    validated; claim text/provenance is never edited.
    """
    status_v = ClaimVerification(status).value if isinstance(status, str) else status.value
    con = inbox._con
    row = con.execute("SELECT * FROM agent_claims WHERE claim_id=?", (claim_id,)).fetchone()
    if row is None:
        raise KeyError(f"unknown_claim: {claim_id}")
    parent_output_id = row["output_id"]

    src_producer = _producer_of_output(inbox, verification_source_output_id)  # raises KeyError if absent
    parent_producer = _producer_of_output(inbox, parent_output_id)
    if src_producer == parent_producer:
        raise SelfVerificationError(
            "self_verification_refused: claim parent "
            f"{parent_output_id!r} and verification source "
            f"{verification_source_output_id!r} share canonical producer identity {parent_producer!r}"
        )

    con.execute(
        "UPDATE agent_claims SET status=?, verification_source_output_id=? WHERE claim_id=?",
        (status_v, verification_source_output_id, claim_id),
    )
    con.commit()
    return {"claim_id": claim_id, "status": status_v,
            "verification_source_output_id": verification_source_output_id}
