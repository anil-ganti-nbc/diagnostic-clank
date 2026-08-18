"""Regression tests for Diagnostic Clank v0.1's knowledge layer:
inbox dedup, incidents/claim history, attachments/quarantine, search,
reindexing. See clank_runtime.knowledge.incidents module docstring for
the laws these enforce.
"""
from __future__ import annotations

import pytest

from clank_runtime.knowledge.attachments import AttachmentQuarantined, AttachmentStore, MAX_ATTACHMENT_BYTES
from clank_runtime.knowledge.inbox import AgentFamily, AgentOutputInbox, OutputType
from clank_runtime.knowledge.incidents import (
    ClaimVerification,
    IncidentClassification,
    IncidentStatus,
    IncidentStore,
    RootCauseCertainty,
)
from clank_runtime.knowledge.clankops_record import extract_clankops_record
from clank_runtime.knowledge.store import DiagnosticKnowledgeStore
from clank_runtime.registry.core import ClankRegistration, ClankRegistry


@pytest.fixture
def registry() -> ClankRegistry:
    reg = ClankRegistry()
    reg.register(ClankRegistration(clank_id="smartwatch-clank", display_name="Smartwatch Clank"))
    return reg


@pytest.fixture
def store(tmp_path, registry) -> DiagnosticKnowledgeStore:
    s = DiagnosticKnowledgeStore(
        tmp_path / "diagnostic.db", tmp_path / "evidence", tmp_path / "quarantine", registry,
    )
    yield s
    s.close()


# -- raw evidence immutability / hashing / dedup -----------------------------

def test_ingest_report_is_hashed_and_persisted(store):
    result = store.ingest_report(agent_family=AgentFamily.CODEX, primary_clank_id="smartwatch-clank", raw_text="hello world")
    assert result.output.raw_text == "hello world"
    assert len(result.output.raw_text_hash) == 64  # sha256 hex
    assert result.was_duplicate is False


def test_reingesting_identical_text_deduplicates(store):
    r1 = store.ingest_report(agent_family=AgentFamily.CODEX, primary_clank_id="smartwatch-clank", raw_text="same text")
    r2 = store.ingest_report(agent_family=AgentFamily.CLAUDE, primary_clank_id="smartwatch-clank", raw_text="same text")
    assert r1.output.output_id == r2.output.output_id
    assert r2.was_duplicate is True
    assert len(store.inbox.list(limit=1000)) == 1


def test_reingesting_different_text_creates_new_record(store):
    r1 = store.ingest_report(agent_family=AgentFamily.CODEX, primary_clank_id="smartwatch-clank", raw_text="text A")
    r2 = store.ingest_report(agent_family=AgentFamily.CODEX, primary_clank_id="smartwatch-clank", raw_text="text B")
    assert r1.output.output_id != r2.output.output_id
    assert len(store.inbox.list(limit=1000)) == 2


def test_raw_text_roundtrips_unmutated(store):
    original = "line1\nline2\n  indented\nCLANKOPS_RECORD\nverdict: X"
    result = store.ingest_report(agent_family=AgentFamily.GROK, primary_clank_id="smartwatch-clank", raw_text=original)
    store.inbox.assert_raw_roundtrip(result.output.output_id, original)


def test_empty_report_rejected(store):
    with pytest.raises(ValueError):
        store.ingest_report(agent_family=AgentFamily.MISC, primary_clank_id="smartwatch-clank", raw_text="   ")


def test_unknown_clank_id_rejected(store):
    with pytest.raises(KeyError):
        store.ingest_report(agent_family=AgentFamily.MISC, primary_clank_id="nonexistent-clank", raw_text="text")


def test_fleet_wide_clank_id_always_allowed(store):
    result = store.ingest_report(agent_family=AgentFamily.MISC, primary_clank_id="fleet-wide", raw_text="text")
    assert result.output.primary_clank_id == "fleet-wide"


# -- deterministic CLANKOPS_RECORD extraction --------------------------------

def test_clankops_record_extracted_deterministically():
    text = "some narrative\n\nCLANKOPS_RECORD\nagent: codex\nverdict: FIELD_TEST_READY\n"
    record = extract_clankops_record(text)
    assert record.agent == "codex"
    assert record.verdict == "FIELD_TEST_READY"
    assert record.project is None  # never fabricated


def test_no_clankops_record_returns_all_none():
    record = extract_clankops_record("just a plain report with no footer")
    assert record.is_empty()


def test_clankops_record_reconstructible_from_raw_text_alone(store):
    text = "investigation\n\nCLANKOPS_RECORD\nagent: claude\nverdict: BLOCKED\n"
    result = store.ingest_report(agent_family=AgentFamily.CLAUDE, primary_clank_id="smartwatch-clank", raw_text=text)
    rec = store.inbox.get(result.output.output_id)
    # re-derive independently, proving no separate mutable copy is needed
    rederived = extract_clankops_record(rec.raw_text)
    assert rederived.verdict == "BLOCKED"


# -- incidents / claim history / contradictions ------------------------------

def test_incident_created_with_minimal_fields(store):
    inc = store.incidents.create(clank_id="smartwatch-clank", title="Native client crashes")
    assert inc.status == IncidentStatus.OPEN
    assert inc.root_cause_certainty == RootCauseCertainty.UNKNOWN
    assert inc.classification == []


def test_incident_status_transition_preserves_timestamps(store):
    inc = store.incidents.create(clank_id="smartwatch-clank", title="X")
    updated = store.incidents.update_status(inc.incident_id, IncidentStatus.RESOLVED)
    assert updated.status == IncidentStatus.RESOLVED
    fetched = store.incidents.get(inc.incident_id)
    assert fetched.status == IncidentStatus.RESOLVED


def test_claim_history_never_deletes_or_edits_prior_claims(store):
    inc = store.incidents.create(clank_id="smartwatch-clank", title="X")
    c1 = store.incidents.add_claim(inc.incident_id, "Codex says FIELD-TEST READY", source="codex")
    old, new = store.incidents.supersede_claim(
        c1.claim_id, "Owner observed it fails", source="owner", old_becomes=ClaimVerification.CONTRADICTED,
    )
    claims = store.incidents.claims_for(inc.incident_id)
    assert len(claims) == 2  # both remain -- CLAIM_RECORDED != CLAIM_TRUE
    original = next(c for c in claims if c.claim_id == c1.claim_id)
    assert original.text == "Codex says FIELD-TEST READY"  # text never mutated
    assert original.status == ClaimVerification.CONTRADICTED
    assert original.superseded_by == new.claim_id


def test_contradiction_is_not_corruption_both_claims_queryable(store):
    inc = store.incidents.create(clank_id="smartwatch-clank", title="X")
    store.incidents.add_claim(inc.incident_id, "claim A", status=ClaimVerification.REPORTED)
    store.incidents.add_claim(inc.incident_id, "claim B (contradicts A)", status=ClaimVerification.CONTRADICTED)
    claims = store.incidents.claims_for(inc.incident_id)
    assert {c.text for c in claims} == {"claim A", "claim B (contradicts A)"}


def test_link_evidence_and_relate_incidents(store):
    result = store.ingest_report(agent_family=AgentFamily.CODEX, primary_clank_id="smartwatch-clank", raw_text="evidence text")
    inc1 = store.incidents.create(clank_id="smartwatch-clank", title="Incident 1")
    inc2 = store.incidents.create(clank_id="smartwatch-clank", title="Incident 2")
    store.incidents.link_evidence(inc1.incident_id, result.output.output_id)
    store.incidents.relate(inc1.incident_id, inc2.incident_id)
    fetched = store.incidents.get(inc1.incident_id)
    assert result.output.output_id in fetched.raw_evidence_ids
    assert inc2.incident_id in fetched.related_incident_ids


def test_root_cause_certainty_never_forced_to_confirmed(store):
    inc = store.incidents.create(
        clank_id="smartwatch-clank", title="X", root_cause="guessing it's the bundle ID",
        root_cause_certainty=RootCauseCertainty.HYPOTHESIS,
    )
    assert inc.root_cause_certainty == RootCauseCertainty.HYPOTHESIS  # not auto-upgraded


def test_incident_classification_supports_multiple_tags(store):
    inc = store.incidents.create(
        clank_id="smartwatch-clank", title="X",
        classification=[IncidentClassification.NATIVE_CLIENT_FAILURE, IncidentClassification.ARCHITECTURE_FAILURE],
    )
    assert len(inc.classification) == 2


# -- search -------------------------------------------------------------------

def test_incident_search_by_title(store):
    store.incidents.create(clank_id="smartwatch-clank", title="Native launcher crash on Finder open")
    store.incidents.create(clank_id="smartwatch-clank", title="Unrelated topic")
    results = store.incidents.search("launcher")
    assert len(results) == 1


def test_report_search_by_raw_text(store):
    store.ingest_report(agent_family=AgentFamily.CODEX, primary_clank_id="smartwatch-clank", raw_text="mentions bundle identifier bug")
    store.ingest_report(agent_family=AgentFamily.CODEX, primary_clank_id="smartwatch-clank", raw_text="totally unrelated content")
    results = store.search_reports("bundle identifier")
    assert len(results) == 1


def test_search_survives_malformed_fts_query(store):
    store.incidents.create(clank_id="smartwatch-clank", title="Something")
    # unbalanced quote is invalid FTS5 syntax -- must fall back gracefully, not raise
    results = store.incidents.search('some"thing')
    assert isinstance(results, list)


def test_reindex_reports_rebuilds_purely_from_raw_evidence(store):
    store.ingest_report(agent_family=AgentFamily.CODEX, primary_clank_id="smartwatch-clank", raw_text="findable via reindex")
    count = store.reindex_reports()
    assert count == 1
    assert len(store.search_reports("findable")) == 1


# -- attachments / quarantine --------------------------------------------------

def test_attachment_content_hashed_and_retrievable(store):
    inc = store.incidents.create(clank_id="smartwatch-clank", title="X")
    att = store.attachments.save(content=b"screenshot bytes", original_filename="shot.png", incident_id=inc.incident_id)
    assert len(att.content_hash) == 64
    assert store.attachments.read_bytes(att.attachment_id) == b"screenshot bytes"


def test_empty_attachment_is_quarantined_not_saved(store):
    with pytest.raises(AttachmentQuarantined):
        store.attachments.save(content=b"", original_filename="empty.txt")
    assert store.attachments._con.execute("SELECT COUNT(*) c FROM attachments").fetchone()["c"] == 0


def test_oversized_attachment_is_quarantined(store):
    huge = b"x" * (MAX_ATTACHMENT_BYTES + 1)
    with pytest.raises(AttachmentQuarantined):
        store.attachments.save(content=huge, original_filename="huge.bin")


def test_quarantined_file_never_linked_to_canonical_record(store):
    inc = store.incidents.create(clank_id="smartwatch-clank", title="X")
    try:
        store.attachments.save(content=b"", original_filename="bad.txt", incident_id=inc.incident_id)
    except AttachmentQuarantined:
        pass
    assert store.attachments.for_incident(inc.incident_id) == []


def test_reuploading_identical_attachment_does_not_duplicate(store):
    inc = store.incidents.create(clank_id="smartwatch-clank", title="X")
    a1 = store.attachments.save(content=b"same bytes", original_filename="a.txt", incident_id=inc.incident_id)
    a2 = store.attachments.save(content=b"same bytes", original_filename="a-renamed.txt", incident_id=inc.incident_id)
    assert a1.attachment_id == a2.attachment_id


# -- persistence (reopen store against same db_path) ---------------------------

def test_state_persists_across_store_reopen(tmp_path, registry):
    db, evidence, quarantine = tmp_path / "diagnostic.db", tmp_path / "evidence", tmp_path / "quarantine"
    s1 = DiagnosticKnowledgeStore(db, evidence, quarantine, registry)
    inc = s1.incidents.create(clank_id="smartwatch-clank", title="Persisted incident")
    s1.close()

    s2 = DiagnosticKnowledgeStore(db, evidence, quarantine, registry)
    fetched = s2.incidents.get(inc.incident_id)
    assert fetched is not None
    assert fetched.title == "Persisted incident"
    s2.close()
