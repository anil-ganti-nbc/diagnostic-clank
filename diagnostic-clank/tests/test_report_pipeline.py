"""Report pipeline + portable paths + REPORT-00x acceptance."""
from __future__ import annotations

from pathlib import Path

import pytest

from clank_runtime.knowledge.inbox import text_hash
from diagnostic_clank.paths import (
    resolve_nas_endpoint,
    resolve_report_paths,
    resolve_state_paths,
    resolved_paths_summary,
)
from diagnostic_clank.report_pipeline import scan_and_ingest, submit_report_text


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    data = tmp_path / "data"
    reports = tmp_path / "reports"
    monkeypatch.setenv("DIAGNOSTIC_DATA_DIR", str(data))
    monkeypatch.setenv("CLANKOPS_REPORT_ROOT", str(reports))
    state = resolve_state_paths()
    rp = resolve_report_paths()
    from diagnostic_clank.report_pipeline import open_store

    store, _ = open_store(state)
    yield store, rp
    store.close()


SAMPLE = """# Beelink China PoC

Investigation notes for Beelink ME Pro HX 470 coverage.

CLANKOPS_RECORD
schema_version: 1
agent: claude
project: oem-radar
task: beelink-china-poc
timestamp: 2026-08-18T10:00:00Z
verdict: partial
unresolved: root cause not fully confirmed
"""


def test_custom_report_root_and_data_dir(isolated):
    store, rp = isolated
    assert "reports" in str(rp.root)
    summary = resolved_paths_summary()
    assert summary["CLANKOPS_REPORT_ROOT"] == str(rp.root)
    assert Path(summary["DIAGNOSTIC_DATA_DIR"]).exists()


def test_report_root_co_locates_with_overridden_data_dir_not_platform_default(tmp_path, monkeypatch):
    """Regression: a deployment (e.g. a container) that overrides
    DIAGNOSTIC_DATA_DIR to a persistent bind mount must get its report
    inbox under that same persistent location by default -- not silently
    under the platform-default home directory, which would vanish on
    container recreation with no error anywhere."""
    persistent = tmp_path / "persistent-bind-mount"
    monkeypatch.setenv("DIAGNOSTIC_DATA_DIR", str(persistent))
    monkeypatch.delenv("CLANKOPS_REPORT_ROOT", raising=False)
    rp = resolve_report_paths()
    assert str(rp.root).startswith(str(persistent))
    assert rp.root == persistent / "clankops-reports"


def test_nas_endpoint_none_when_unconfigured(tmp_path, monkeypatch):
    monkeypatch.setenv("DIAGNOSTIC_DATA_DIR", str(tmp_path / "home"))
    monkeypatch.delenv("DIAGNOSTIC_CLANK_NAS_URL", raising=False)
    assert resolve_nas_endpoint() is None


def test_nas_endpoint_env_var_takes_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv("DIAGNOSTIC_DATA_DIR", str(tmp_path / "home"))
    monkeypatch.setenv("DIAGNOSTIC_CLANK_NAS_URL", "http://192.0.2.1:8420/")
    assert resolve_nas_endpoint() == "http://192.0.2.1:8420/"


def test_nas_endpoint_reads_local_config_file(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("DIAGNOSTIC_DATA_DIR", str(home))
    monkeypatch.delenv("DIAGNOSTIC_CLANK_NAS_URL", raising=False)
    (home / "nas-endpoint.txt").write_text("# comment\nhttp://192.0.2.1:8420/\n")
    assert resolve_nas_endpoint() == "http://192.0.2.1:8420/"


def test_paths_with_spaces(tmp_path, monkeypatch):
    data = tmp_path / "app data"
    reports = tmp_path / "clank reports"
    monkeypatch.setenv("DIAGNOSTIC_DATA_DIR", str(data))
    monkeypatch.setenv("CLANKOPS_REPORT_ROOT", str(reports))
    rp = resolve_report_paths()
    assert rp.inbox.is_dir()


def test_report_001_valid_ingest(isolated):
    store, rp = isolated
    path = submit_report_text(
        SAMPLE,
        agent="claude",
        project="oem-radar",
        task="beelink-china-poc",
        report_paths=rp,
    )
    assert path.exists()
    result = scan_and_ingest(store, rp)
    assert result.ingested == 1
    assert result.outcomes[0].status == "ingested"
    assert result.outcomes[0].clankops is not None
    assert result.outcomes[0].clankops.project == "oem-radar"
    assert not (rp.inbox / path.name).exists()
    processed = next(p for p in rp.processed.iterdir() if p.name == path.name)
    # raw preserved
    rec = store.inbox.get(result.outcomes[0].output_id)
    assert rec is not None
    submitted_raw = processed.read_bytes().decode("utf-8")
    assert rec.raw_text == submitted_raw
    assert rec.raw_text_hash == text_hash(submitted_raw)
    assert "Beelink China PoC" in rec.raw_text


def test_report_002_exact_duplicate(isolated):
    store, rp = isolated
    submit_report_text(SAMPLE, agent="claude", project="oem-radar", task="t1", report_paths=rp)
    scan_and_ingest(store, rp)
    # resubmit identical body
    submit_report_text(SAMPLE, agent="claude", project="oem-radar", task="t2", report_paths=rp)
    result = scan_and_ingest(store, rp)
    assert result.duplicates == 1
    assert store.inbox.list(limit=100)  # at least one
    # only one unique hash
    hashes = {r.raw_text_hash for r in store.inbox.list(limit=100)}
    assert len(hashes) == 1


def test_report_004_quarantine_empty_and_bad_name(isolated):
    store, rp = isolated
    (rp.inbox / "empty.md").write_text("   \n", encoding="utf-8")
    (rp.inbox / "evil.bin").write_bytes(b"\x00\x01\x02")
    result = scan_and_ingest(store, rp)
    assert result.quarantined >= 2
    assert store.inbox.list(limit=10) == []


def test_report_005_unknown_not_invented(isolated):
    store, rp = isolated
    body = """# Open miss\n\nRoot cause: UNKNOWN\n\nCLANKOPS_RECORD\nagent: grok\nproject: oem-radar\ntask: open-miss\nunresolved: root cause unknown\nverdict: open\n"""
    submit_report_text(body, agent="grok", project="oem-radar", task="open-miss", report_paths=rp)
    result = scan_and_ingest(store, rp)
    assert result.ingested == 1
    cop = result.outcomes[0].clankops
    assert cop is not None
    assert "unknown" in (cop.unresolved or "").lower() or cop.verdict == "open"


def test_cwd_irrelevant(isolated, tmp_path, monkeypatch):
    store, rp = isolated
    other = tmp_path / "other cwd"
    other.mkdir()
    monkeypatch.chdir(other)
    submit_report_text(SAMPLE, agent="claude", project="oem-radar", task="cwd", report_paths=rp)
    result = scan_and_ingest(store, rp)
    assert result.ingested == 1
    assert list(other.iterdir()) == []


def test_hash_identity_not_path(isolated):
    store, rp = isolated
    p1 = submit_report_text(SAMPLE, agent="claude", project="oem-radar", task="a", report_paths=rp)
    scan_and_ingest(store, rp)
    canonical = store.inbox.list(limit=10)
    assert len(canonical) == 1
    renamed = rp.inbox / "relocated-report.md"
    renamed.write_bytes((rp.processed / p1.name).read_bytes())
    result = scan_and_ingest(store, rp)
    assert result.duplicates == 1
    assert len(store.inbox.list(limit=10)) == 1
    assert result.outcomes[0].content_hash == canonical[0].raw_text_hash


def test_invalid_utf8_is_quarantined_byte_for_byte(isolated):
    store, rp = isolated
    original = b"valid prefix\xff\xfe\n"
    path = rp.inbox / "invalid.md"
    path.write_bytes(original)
    result = scan_and_ingest(store, rp)
    assert result.quarantined == 1
    quarantined = rp.quarantine / "invalid.md"
    assert quarantined.read_bytes() == original
    assert store.inbox.list(limit=10) == []


def test_malformed_clankops_footer_is_quarantined(isolated):
    store, rp = isolated
    original = b"report\n\nCLANKOPS_RECORD\nagent claude\nverdict: open\n"
    path = rp.inbox / "malformed.md"
    path.write_bytes(original)
    result = scan_and_ingest(store, rp)
    assert result.quarantined == 1
    assert result.outcomes[0].quarantine_reason.startswith("malformed_clankops_record:")
    assert (rp.quarantine / path.name).read_bytes() == original
    assert store.inbox.list(limit=10) == []
