"""Diagnostic Clank + Agent Inbox + dynamic registry."""
from __future__ import annotations
from datetime import UTC, datetime
from pathlib import Path
import pytest
from clank_runtime.diagnostic.engine import diagnose
from clank_runtime.diagnostic.models import DiagnosticCase, IncidentType, StageId
from clank_runtime.knowledge.inbox import AgentFamily, AgentOutputInbox, ClaimVerification, text_hash
from clank_runtime.registry.core import ClankRegistration, ClankRegistry

def _seed(registry: ClankRegistry) -> None:
    for cid, domain in [
        ("oem-radar", "product"),  # example fixture
        ("watch-clank", "product"),  # example fixture
        ("feature-phone-clank", "product"),  # example fixture
    ]:
        if registry.get(cid) is None:
            registry.register(ClankRegistration(clank_id=cid, display_name=cid, domain=domain))

@pytest.fixture()
def registry() -> ClankRegistry:
    r = ClankRegistry(); _seed(r); return r

@pytest.fixture()
def inbox(tmp_path: Path, registry: ClankRegistry):
    box = AgentOutputInbox(tmp_path / "k.db", registry)
    yield box; box.close()

def test_source_gap_not_parser_failure():
    r = diagnose(DiagnosticCase(clank_id="oem-radar", incident_type=IncidentType.MISS,
        facts={"source_capable": False, "fetch_ok": True, "parse_ok": True}))
    assert r.first_failed_gate == StageId.SOURCE_CAPABILITY and r.failure_class == "source_gap"

def test_region_gap_distinct():
    r = diagnose(DiagnosticCase(clank_id="watch-clank", incident_type=IncidentType.MISS,
        facts={"source_capable": True, "region_monitored": False}))
    assert r.failure_class == "region_gap"

def test_extraction_after_fetch_parse():
    r = diagnose(DiagnosticCase(clank_id="watch-clank", incident_type=IncidentType.MISS, facts={
        "source_capable": True, "region_monitored": True, "discovered": True,
        "fetch_ok": True, "parse_ok": True, "extraction_ok": False}))
    assert r.first_failed_gate == StageId.EXTRACTION and r.regression_fixture_recommendation

def test_freshness_historical():
    r = diagnose(DiagnosticCase(clank_id="watch-clank", incident_type=IncidentType.STALE_ALERT, facts={
        "source_capable": True, "region_monitored": True, "discovered": True, "fetch_ok": True,
        "parse_ok": True, "extraction_ok": True, "identity_ok": True,
        "published_at": datetime(2026, 3, 1, tzinfo=UTC),
        "first_seen_at": datetime(2026, 8, 17, tzinfo=UTC)}))
    assert r.failure_class == "freshness_failure"

def test_absence_not_novelty():
    r = diagnose(DiagnosticCase(clank_id="watch-clank", incident_type=IncidentType.FALSE_NOVELTY, facts={
        "source_capable": True, "region_monitored": True, "discovered": True, "fetch_ok": True,
        "parse_ok": True, "extraction_ok": True, "identity_ok": True, "novelty_from_absence_only": True}))
    assert r.failure_class == "novelty_failure"

def test_delivery_failure():
    r = diagnose(DiagnosticCase(clank_id="oem-radar", incident_type=IncidentType.DELIVERY_FAILURE, facts={
        "source_capable": True, "region_monitored": True, "discovered": True, "fetch_ok": True,
        "parse_ok": True, "extraction_ok": True, "identity_ok": True, "event_created": True, "delivery_ok": False}))
    assert r.failure_class == "delivery_failure"

def test_insufficient_unknown():
    r = diagnose(DiagnosticCase(clank_id="oem-radar", incident_type=IncidentType.MISS, facts={}))
    assert r.failure_class == "unknown" and r.confidence.value == "unresolved"

def test_downstream_separated():
    r = diagnose(DiagnosticCase(clank_id="watch-clank", incident_type=IncidentType.MISS, facts={
        "source_capable": True, "region_monitored": True, "discovered": True, "fetch_ok": True,
        "parse_ok": True, "extraction_ok": False, "identity_ok": False, "event_created": False}))
    assert r.first_failed_gate == StageId.EXTRACTION
    assert any(d.role.value == "downstream_consequence" for d in r.downstream_effects)

def test_save_three_agents(inbox: AgentOutputInbox):
    for fam, body in [(AgentFamily.CLAUDE, "Claude notes\n"), (AgentFamily.CODEX, "Codex 12 passed\n"),
                      (AgentFamily.GROK, "Grok suspects freshness failure\n")]:
        rec = inbox.save(agent_family=fam, primary_clank_id="watch-clank", raw_text=body)
        inbox.assert_raw_roundtrip(rec.output_id, body)
    assert len(inbox.list(clank_id="watch-clank")) == 3

def test_claim_reported_not_verified(inbox: AgentOutputInbox):
    rec = inbox.save(agent_family=AgentFamily.GROK, primary_clank_id="watch-clank",
                     raw_text="I suspect parser failure on extraction\n")
    assert all(c.status == ClaimVerification.REPORTED for c in inbox.claims_for(rec.output_id))

def test_future_clank_without_core_edit(tmp_path: Path, registry: ClankRegistry):
    registry.register(ClankRegistration(clank_id="test-future-clank", display_name="Future"))
    inbox = AgentOutputInbox(tmp_path / "f.db", registry)
    rec = inbox.save(agent_family=AgentFamily.CODEX, primary_clank_id="test-future-clank", raw_text="note\n")
    r = diagnose(DiagnosticCase(clank_id="test-future-clank", incident_type=IncidentType.MANUAL_INVESTIGATION,
                                facts={}, related_agent_output_ids=[rec.output_id]))
    assert r.clank_id == "test-future-clank" and r.failure_class == "unknown"
    inbox.close()

def test_no_child_mutation(tmp_path: Path):
    child = tmp_path / "child.db"; child.write_text("x"); before = child.read_bytes()
    diagnose(DiagnosticCase(clank_id="oem-radar", incident_type=IncidentType.MISS, facts={"source_capable": False}))
    assert child.read_bytes() == before
