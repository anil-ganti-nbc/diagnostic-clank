"""Backup/restore regression coverage -- application-consistent snapshot of
the local knowledge state, restored into a fully isolated destination,
with content-hash round-trip verification. See diagnostic_clank.backup.
"""
from __future__ import annotations

import sqlite3

import pytest

from clank_runtime.knowledge.inbox import AgentFamily
from clank_runtime.knowledge.incidents import IncidentStatus
from diagnostic_clank.backup import create_backup, load_manifest, restore_backup
from diagnostic_clank.paths import resolve_state_paths
from diagnostic_clank.report_pipeline import open_store


@pytest.fixture()
def live(tmp_path, monkeypatch):
    data = tmp_path / "live-data"
    monkeypatch.setenv("DIAGNOSTIC_DATA_DIR", str(data))
    state = resolve_state_paths()
    store, _ = open_store(state)
    inc = store.incidents.create(
        clank_id="fleet-wide",
        title="Test incident for backup/restore coverage",
        status=IncidentStatus.OPEN,
        observed_behaviour="Synthetic fixture incident, not real field data.",
    )
    store.incidents.add_claim(inc.incident_id, "original claim", source="test")
    ingest = store.ingest_report(
        agent_family=AgentFamily.MISC,
        primary_clank_id="fleet-wide",
        raw_text="# Fixture report\n\nBody text for backup/restore test.\n",
    )
    store.attachments.save(
        content=b"fixture attachment bytes for backup/restore test\n",
        original_filename="fixture.txt",
        incident_id=inc.incident_id,
    )
    yield store, state, inc.incident_id, ingest.output.output_id
    store.close()


def test_backup_creates_consistent_single_file_db_with_manifest(live, tmp_path):
    store, state, _inc_id, _output_id = live
    dest = tmp_path / "backup-1"
    manifest = create_backup(state, dest, source_repo_revision="deadbeef")

    assert (dest / "diagnostic.db").is_file()
    assert not (dest / "diagnostic.db-wal").exists()
    assert not (dest / "diagnostic.db-shm").exists()
    assert manifest.counts["incidents"] == 1
    assert manifest.counts["incident_claims"] == 1
    assert manifest.counts["agent_outputs"] == 1
    assert manifest.counts["attachments"] == 1
    assert "diagnostic.db" in manifest.checksums
    assert manifest.source_repo_revision == "deadbeef"

    con = sqlite3.connect(dest / "diagnostic.db")
    try:
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        con.close()

    loaded = load_manifest(dest)
    assert loaded is not None
    assert loaded.counts == manifest.counts


def test_backup_is_safe_against_a_live_wal_writer(live, tmp_path):
    """The source DB stays open (WAL mode, as the packaged app leaves it)
    for the entire backup -- this must not corrupt or block indefinitely."""
    store, state, inc_id, _output_id = live
    # simulate more writes happening around the backup call
    store.incidents.add_claim(inc_id, "a second claim, written just before backup", source="test")
    dest = tmp_path / "backup-live"
    manifest = create_backup(state, dest)
    assert manifest.counts["incident_claims"] == 2


def test_restore_into_isolated_destination_never_touches_source(live, tmp_path):
    store, state, inc_id, output_id = live
    backup_dir = tmp_path / "backup-2"
    create_backup(state, backup_dir)

    restore_dir = tmp_path / "restored-isolated"
    restored = restore_backup(backup_dir, restore_dir)

    assert restored.home == restore_dir
    assert restored.db_path != state.db_path
    assert restored.db_path.is_file()

    con = sqlite3.connect(restored.db_path)
    try:
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert con.execute("SELECT COUNT(*) FROM incidents").fetchone()[0] == 1
        assert con.execute("SELECT title FROM incidents").fetchone()[0] == (
            "Test incident for backup/restore coverage"
        )
    finally:
        con.close()

    # source (live) DB is completely untouched by the restore
    live_con = sqlite3.connect(state.db_path)
    try:
        assert live_con.execute("SELECT COUNT(*) FROM incidents").fetchone()[0] == 1
        assert live_con.execute(
            "SELECT incident_id FROM incidents"
        ).fetchone()[0] == inc_id
    finally:
        live_con.close()


def test_round_trip_content_hash_matches_for_raw_report_and_attachment(live, tmp_path):
    store, state, inc_id, output_id = live
    original_report = store.inbox.get(output_id)
    assert original_report is not None
    original_hash = original_report.raw_text_hash

    atts = store.attachments.for_incident(inc_id)
    assert len(atts) == 1
    original_attachment_bytes = store.attachments.read_bytes(atts[0].attachment_id)

    backup_dir = tmp_path / "backup-3"
    create_backup(state, backup_dir)
    restore_dir = tmp_path / "restored-3"
    restored = restore_backup(backup_dir, restore_dir)

    from clank_runtime.knowledge.store import DiagnosticKnowledgeStore

    restored_store = DiagnosticKnowledgeStore(
        restored.db_path, restored.evidence_dir, restored.quarantine_dir
    )
    try:
        restored_report = restored_store.inbox.get(output_id)
        assert restored_report is not None
        assert restored_report.raw_text_hash == original_hash
        assert restored_report.raw_text == original_report.raw_text

        restored_atts = restored_store.attachments.for_incident(inc_id)
        assert len(restored_atts) == 1
        assert restored_atts[0].content_hash == atts[0].content_hash
        restored_bytes = restored_store.attachments.read_bytes(restored_atts[0].attachment_id)
        assert restored_bytes == original_attachment_bytes
    finally:
        restored_store.close()


def test_restore_rejects_missing_backup(tmp_path):
    with pytest.raises(FileNotFoundError):
        restore_backup(tmp_path / "does-not-exist", tmp_path / "dest")
