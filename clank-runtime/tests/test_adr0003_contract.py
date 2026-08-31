"""ADR-0003 contract tests: schema v2 (external_ref), recommendation version
history, append-only operator dispositions, claim-verification transitions
with canonical-producer self-verification prevention.

Governing text: ADR-0003 (ratification + Inbox bridge), sections 2, 4, 5.
"""
from __future__ import annotations

import sqlite3

import pytest

from clank_runtime.knowledge.dispositions import (
    Disposition,
    RecommendationDispositionStore,
    SelfVerificationError,
    canonical_producer_identity,
    transition_claim,
)
from clank_runtime.knowledge.inbox import (
    AgentFamily,
    AgentOutputInbox,
    ClaimVerification,
    OutputType,
)
from clank_runtime.registry.core import ClankRegistration, ClankRegistry


@pytest.fixture
def registry() -> ClankRegistry:
    reg = ClankRegistry()
    reg.register(ClankRegistration(clank_id="watch-clank", display_name="Watch Clank"))
    reg.register(ClankRegistration(clank_id="smartphone-clank", display_name="Smartphone Clank"))
    return reg


@pytest.fixture
def inbox(tmp_path, registry) -> AgentOutputInbox:
    db = AgentOutputInbox(tmp_path / "inbox.db", registry)
    yield db
    db.close()


# -- A1: enum surface --------------------------------------------------------

def test_recommendation_output_type_exists():
    assert OutputType.RECOMMENDATION.value == "recommendation"


def test_no_motherclank_agent_family_exists():
    assert not hasattr(AgentFamily, "MOTHERCLANK")
    assert {f.name for f in AgentFamily} == {"CLAUDE", "CODEX", "GROK", "MISC"}


# -- A2: schema v2 migration / compatibility ---------------------------------

def _make_v1_db(path, registry) -> None:
    """Create a genuine v1 database using the ORIGINAL v1 schema DDL."""
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS agent_outputs (
            output_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, agent_family TEXT NOT NULL,
            primary_clank_id TEXT NOT NULL, related_clank_ids_json TEXT NOT NULL DEFAULT '[]',
            output_type TEXT NOT NULL, raw_text TEXT NOT NULL, raw_text_hash TEXT NOT NULL,
            related_diagnostic_case_id TEXT, related_git_revision TEXT, misc_source TEXT,
            session_label TEXT
        );
        CREATE TABLE IF NOT EXISTS agent_claims (
            claim_id TEXT PRIMARY KEY, output_id TEXT NOT NULL, text TEXT NOT NULL,
            status TEXT NOT NULL, verification_source_output_id TEXT
        );
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO agent_outputs VALUES (
            'legacy-row', '2026-08-01T00:00:00+00:00', 'codex', 'fleet-wide',
            '[]', 'general_note', 'legacy text',
            'a' * 64, NULL, NULL, NULL, NULL);
        INSERT INTO meta VALUES ('schema_version','1');
    """)
    con.commit()
    con.close()


def test_v1_to_v2_migration_preserves_rows_and_sets_version(tmp_path, registry):
    p = tmp_path / "v1.db"
    _make_v1_db(p, registry)
    inbox = AgentOutputInbox(p, registry)  # triggers migration
    try:
        assert inbox.schema_version() == "2"
        legacy = inbox.get("legacy-row")
        assert legacy is not None and legacy.raw_text == "legacy text"
        assert legacy.external_ref is None  # pre-existing rows read as NULL
    finally:
        inbox.close()


def test_fresh_db_reports_schema_v2(inbox):
    assert inbox.schema_version() == "2"


# -- A2/A3: external_ref round-trip and version history -----------------------

def test_external_ref_roundtrip(inbox):
    rec = inbox.save(
        agent_family=AgentFamily.MISC, primary_clank_id="watch-clank",
        raw_text="rec body v1", output_type=OutputType.RECOMMENDATION,
        misc_source="motherclank-m3/m3-r1", external_ref="rec-abc123",
    )
    fetched = inbox.get(rec.output_id)
    assert fetched.external_ref == "rec-abc123"
    assert fetched.output_type == OutputType.RECOMMENDATION
    assert fetched.misc_source == "motherclank-m3/m3-r1"


def test_identical_content_dedups_regardless_of_external_ref(inbox):
    r1 = inbox.save(agent_family=AgentFamily.MISC, primary_clank_id="watch-clank",
                    raw_text="identical body", misc_source="m", external_ref="rec-x")
    dups: list[str] = []
    r2 = inbox.save(agent_family=AgentFamily.MISC, primary_clank_id="watch-clank",
                    raw_text="identical body", misc_source="m", external_ref="rec-x",
                    _duplicate_of=dups)
    assert r1.output_id == r2.output_id  # content dedup still canonical behavior
    assert dups == [r1.output_id]


def test_changed_content_same_external_ref_creates_new_immutable_row(inbox):
    v1 = inbox.save(agent_family=AgentFamily.MISC, primary_clank_id="watch-clank",
                    raw_text="version one", output_type=OutputType.RECOMMENDATION,
                    misc_source="motherclank-m3/m3-r1", external_ref="rec-v")
    v2 = inbox.save(agent_family=AgentFamily.MISC, primary_clank_id="watch-clank",
                    raw_text="version two with new citations",
                    output_type=OutputType.RECOMMENDATION,
                    misc_source="motherclank-m3/m3-r1", external_ref="rec-v")
    assert v1.output_id != v2.output_id          # new immutable row
    assert inbox.get(v1.output_id).raw_text == "version one"  # earlier version intact
    assert inbox.get(v2.output_id).external_ref == "rec-v"    # same logical identity


def test_deterministic_latest_version_ordering(inbox):
    a = inbox.save(agent_family=AgentFamily.MISC, primary_clank_id="watch-clank",
                   raw_text="earliest", misc_source="m", external_ref="rec-o",
                   session_label=None)
    b = inbox.save(agent_family=AgentFamily.MISC, primary_clank_id="watch-clank",
                   raw_text="middle", misc_source="m", external_ref="rec-o")
    c = inbox.save(agent_family=AgentFamily.MISC, primary_clank_id="watch-clank",
                   raw_text="latest", misc_source="m", external_ref="rec-o")
    latest = inbox.latest_by_external_ref("rec-o")
    # deterministic order (created_at ASC, output_id ASC); ties on created_at
    # fall to output_id, so the result is stable regardless of insertion luck.
    expected_last = sorted([a, b, c],
                           key=lambda r: (r.created_at.isoformat(), r.output_id))[-1]
    assert latest.output_id == expected_last.output_id


# -- A4: dispositions ---------------------------------------------------------

@pytest.fixture
def dispositions(inbox) -> RecommendationDispositionStore:
    from clank_runtime.knowledge.dispositions import ensure_disposition_tables
    ensure_disposition_tables(inbox._con)
    return RecommendationDispositionStore(inbox)


def test_dispositions_stored_independently_of_claim_verification(inbox, dispositions):
    out = inbox.save(agent_family=AgentFamily.MISC, primary_clank_id="watch-clank",
                     raw_text="rec for disposition", misc_source="m", external_ref="rec-d")
    claims_before = inbox.claims_for(out.output_id)
    dispositions.record(external_ref="rec-d", disposition=Disposition.ACT,
                        decided_by="operator", decided_at="2026-08-22T12:00:00Z")
    assert inbox.claims_for(out.output_id) == claims_before      # untouched
    hist = dispositions.history("rec-d")
    assert len(hist) == 1 and hist[0].disposition == Disposition.ACT


def test_revised_disposition_appends_new_row_not_update(dispositions):
    dispositions.record(external_ref="rec-r", disposition=Disposition.DEFER,
                        decided_by="operator", decided_at="2026-08-22T10:00:00Z")
    dispositions.record(external_ref="rec-r", disposition=Disposition.DISMISS,
                        decided_by="operator", decided_at="2026-08-22T11:00:00Z")
    hist = dispositions.history("rec-r")
    assert [d.disposition for d in hist] == [Disposition.DEFER, Disposition.DISMISS]
    assert hist[0].disposition_id != hist[1].disposition_id
    assert dispositions.latest("rec-r").disposition == Disposition.DISMISS


def test_disposition_update_rejected_at_sqlite_level(inbox, dispositions):
    rec = dispositions.record(external_ref="rec-u", disposition=Disposition.ACT,
                              decided_by="operator", decided_at="2026-08-22T09:00:00Z")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        inbox._con.execute(
            "UPDATE recommendation_dispositions SET disposition='DISMISS' WHERE disposition_id=?",
            (rec.disposition_id,))
    inbox._con.rollback()


def test_disposition_delete_rejected_at_sqlite_level(inbox, dispositions):
    rec = dispositions.record(external_ref="rec-del", disposition=Disposition.DEFER,
                              decided_by="operator", decided_at="2026-08-22T09:00:00Z")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        inbox._con.execute(
            "DELETE FROM recommendation_dispositions WHERE disposition_id=?",
            (rec.disposition_id,))
    inbox._con.rollback()


def test_invalid_disposition_value_rejected_by_check_constraint(inbox):
    """Bypass the enum to prove the DB CHECK constraint rejects bad values."""
    from clank_runtime.knowledge.dispositions import ensure_disposition_tables
    ensure_disposition_tables(inbox._con)
    con = inbox._con
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            """INSERT INTO recommendation_dispositions
               (disposition_id, external_ref, disposition, decided_by, decided_at, note)
               VALUES ('x', 'rec-bad', 'MAYBE', 'operator', '2026-08-22T09:00:00Z', NULL)""")
        con.commit()


# -- A5: claim verification transitions ---------------------------------------

def _claim_on(inbox, tmp_text="line with failure keyword") -> str:
    rec = inbox.save(agent_family=AgentFamily.CODEX, primary_clank_id="watch-clank",
                     raw_text=f"report\n{tmp_text}\n")
    return inbox.claims_for(rec.output_id)[0].claim_id


def test_canonical_identity_misc_misc_source_participates():
    class R:
        pass
    a, b = R(), R()
    a.agent_family, a.misc_source, a.agent_name = AgentFamily.MISC, "motherclank-m3/m3-r1", None
    b.agent_family, b.misc_source, b.agent_name = AgentFamily.MISC, "other-tool/v9", None
    assert canonical_producer_identity(a) == ("misc", "motherclank-m3/m3-r1")
    assert canonical_producer_identity(a) != canonical_producer_identity(b)


def test_same_producer_self_verification_rejected(inbox):
    parent = inbox.save(agent_family=AgentFamily.CODEX, primary_clank_id="watch-clank",
                        raw_text="finding\nfailure detected here\n")
    source = inbox.save(agent_family=AgentFamily.CODEX, primary_clank_id="watch-clank",
                        raw_text="corroborating evidence from same producer")
    claim_id = inbox.claims_for(parent.output_id)[0].claim_id
    with pytest.raises(SelfVerificationError, match="self_verification_refused"):
        transition_claim(inbox, claim_id=claim_id,
                         status=ClaimVerification.CORROBORATED,
                         verification_source_output_id=source.output_id)


def test_same_family_different_misc_source_allowed(inbox):
    parent = inbox.save(agent_family=AgentFamily.MISC, primary_clank_id="watch-clank",
                        raw_text="machine finding\nfailure signature present\n",
                        misc_source="motherclank-m3/m3-r1")
    source = inbox.save(agent_family=AgentFamily.MISC, primary_clank_id="watch-clank",
                        raw_text="independent tool corroborates", misc_source="verifier-tool/v2")
    claim_id = inbox.claims_for(parent.output_id)[0].claim_id
    res = transition_claim(inbox, claim_id=claim_id,
                           status=ClaimVerification.VERIFIED,
                           verification_source_output_id=source.output_id)
    assert res["verification_source_output_id"] == source.output_id


def test_different_family_verification_allowed_and_persists(inbox):
    parent = inbox.save(agent_family=AgentFamily.CODEX, primary_clank_id="watch-clank",
                        raw_text="claude-era finding\nfailure noted\n")
    source = inbox.save(agent_family=AgentFamily.GROK, primary_clank_id="watch-clank",
                        raw_text="grok independently confirms the finding")
    claim_id = inbox.claims_for(parent.output_id)[0].claim_id
    res = transition_claim(inbox, claim_id=claim_id,
                           status=ClaimVerification.CORROBORATED,
                           verification_source_output_id=source.output_id)
    row = inbox._con.execute(
        "SELECT status, verification_source_output_id FROM agent_claims WHERE claim_id=?",
        (claim_id,)).fetchone()
    assert row["status"] == ClaimVerification.CORROBORATED.value
    assert row["verification_source_output_id"] == source.output_id


def test_missing_verification_source_fails_closed(inbox):
    parent = inbox.save(agent_family=AgentFamily.GROK, primary_clank_id="watch-clank",
                        raw_text="finding\nfailure again\n")
    claim_id = inbox.claims_for(parent.output_id)[0].claim_id
    with pytest.raises(KeyError, match="unknown_output"):
        transition_claim(inbox, claim_id=claim_id,
                         status=ClaimVerification.CORROBORATED,
                         verification_source_output_id="nonexistent-output-id")


def test_unknown_claim_fails_closed(inbox):
    with pytest.raises(KeyError, match="unknown_claim"):
        transition_claim(inbox, claim_id="no-such-claim",
                         status=ClaimVerification.VERIFIED,
                         verification_source_output_id="any")


def test_misc_self_verification_via_shared_misc_source_rejected(inbox):
    parent = inbox.save(agent_family=AgentFamily.MISC, primary_clank_id="watch-clank",
                        raw_text="supervisory finding\nfailure pattern x\n",
                        misc_source="motherclank-m3/m3-r1")
    source = inbox.save(agent_family=AgentFamily.MISC, primary_clank_id="watch-clank",
                        raw_text="same tool re-checks itself", misc_source="motherclank-m3/m3-r1")
    claim_id = inbox.claims_for(parent.output_id)[0].claim_id
    with pytest.raises(SelfVerificationError):
        transition_claim(inbox, claim_id=claim_id,
                         status=ClaimVerification.VERIFIED,
                         verification_source_output_id=source.output_id)


# -- existing invariants still hold -------------------------------------------

def test_raw_hash_semantics_untouched(inbox):
    rec = inbox.save(agent_family=AgentFamily.MISC, primary_clank_id="watch-clank",
                     raw_text="hash check", misc_source="m", external_ref="rec-h")
    assert len(rec.raw_text_hash) == 64


def test_motherclank_recommendation_text_does_not_set_git_revision(inbox):
    """Motherclank M3 text contains rec-<16hex> and sha256:<64hex>.
    Those must not be stored as related_git_revision."""
    from clank_runtime.knowledge.inbox import extract_related_git_revision

    rec_id = "rec-" + "ab" * 8
    content = "a" * 64
    text = (
        f"RECOMMENDATION {rec_id}\n"
        "title: Stale run detected on watch-clank\n"
        "clank: watch-clank\n"
        f"chain_hash: sha256:{content}\n"
        f"generated_from: 2026-08-22T07:39:55+00:00 batch_hash: sha256:{content}\n"
        "ADVISORY ONLY — operator owns every decision; Motherclank executes nothing.\n"
    )
    assert extract_related_git_revision(text) is None
    rec = inbox.save(
        agent_family=AgentFamily.MISC, primary_clank_id="watch-clank",
        raw_text=text, output_type=OutputType.RECOMMENDATION,
        misc_source="motherclank-m3/m3-r1", external_ref=rec_id,
    )
    assert rec.related_git_revision is None


def test_extract_related_git_revision_accepts_exact_40_char_sha():
    from clank_runtime.knowledge.inbox import extract_related_git_revision

    sha = "e20eeb3c" + "0" * 32
    assert len(sha) == 40
    text = f"checkout at {sha} for watch-clank"
    assert extract_related_git_revision(text) == sha


def test_extract_related_git_revision_skips_short_hex_and_sha256_prefix():
    from clank_runtime.knowledge.inbox import extract_related_git_revision

    assert extract_related_git_revision("rec-abcdef0123456789") is None
    assert extract_related_git_revision("sha256:" + "ab" * 32) is None
    assert extract_related_git_revision("deadbee") is None
