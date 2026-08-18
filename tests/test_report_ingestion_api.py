import json
import threading
import urllib.request
from pathlib import Path

from clank_runtime.knowledge.report_ingestion import ReportIngestionStore
from clank_runtime.registry.core import ClankRegistration, ClankRegistry
from diagnostic_clank.dashboard import serve
from diagnostic_clank.paths import resolve_state_paths


def make_store(tmp_path: Path) -> ReportIngestionStore:
    registry = ClankRegistry()
    registry.register(ClankRegistration(clank_id="oem-radar"))
    registry.register(ClankRegistration(clank_id="watch-clank"))
    return ReportIngestionStore(tmp_path / "knowledge.db", tmp_path / "raw", registry)


def test_register_is_chunked_and_candidate_stays_unverified(tmp_path: Path):
    store = make_store(tmp_path)
    source = """----------
L-OEM-001 — Example miss
----------
STATUS:
CANDIDATE / PROVENANCE REQUIRED
ROOT CAUSE:
SOURCE_GAP
LESSON:
UNKNOWN > CONFIDENTLY WRONG
""".encode()
    result = store.ingest_bytes(
        source, source_agent="GROK", filename="historical-register.md"
    )
    findings = store.rows("report_findings", result["report_id"])
    assert result["status"] == "complete"
    assert result["chunks_total"] == 1
    assert findings[0]["epistemic_status"] == "CANDIDATE / PROVENANCE REQUIRED"
    assert findings[0]["review_status"] == "AUTO_EXTRACTED"
    assert store.rows("report_lessons", result["report_id"])


def test_exact_duplicate_is_idempotent(tmp_path: Path):
    store = make_store(tmp_path)
    source = b"a" * 200_000
    first = store.ingest_bytes(source, source_agent="IMPORT")
    duplicate = store.ingest_bytes(source, source_agent="IMPORT")
    assert first["status"] == "complete"
    assert duplicate["status"] == "duplicate"
    assert len(store.list_reports()) == 1


def test_reprocessing_keeps_previous_revision(tmp_path: Path):
    store = make_store(tmp_path)
    result = store.ingest_bytes(
        "L-WATCH-001 — Watch finding\n".encode(), source_agent="HUMAN"
    )
    report_id = result["report_id"]
    second = store.process(report_id)
    assert second["processing_revision"] == 2
    assert store.rows("report_chunks", report_id, revision=1)
    assert store.rows("report_chunks", report_id, revision=2)


def test_raw_hash_and_unknown_mapping_are_preserved(tmp_path: Path):
    store = make_store(tmp_path)
    result = store.ingest_bytes(b"future clank report", source_agent="CODEX")
    report = store.get(result["report_id"])
    assert report["sha256"] == result["sha256"]
    assert report["primary_clank_id"] is None


def test_http_api_returns_report_and_derived_findings(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DIAGNOSTIC_CLANK_HOME", str(tmp_path / "home"))
    server, store = serve(resolve_state_paths(), port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body = "----------\nL-OEM-001 — API finding\n----------\nSTATUS:\nCANDIDATE / PROVENANCE REQUIRED\n".encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{server.server_address[1]}/api/v1/reports",
            data=body,
            headers={"Content-Type": "text/plain", "X-Source-Agent": "CODEX"},
            method="POST",
        )
        with urllib.request.urlopen(req) as response:
            payload = json.loads(response.read())
            assert response.status == 201
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_address[1]}/api/v1/reports/{payload['report_id']}/incidents"
        ) as response:
            findings = json.loads(response.read())["incidents"]
        assert findings[0]["epistemic_status"] == "CANDIDATE / PROVENANCE REQUIRED"
    finally:
        server.shutdown()
        store.close()
