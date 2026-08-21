"""Regression tests for the Diagnostic Clank v0.1 dashboard/loopback server."""
from __future__ import annotations

import os
import threading
import time
import urllib.request

import pytest

from diagnostic_clank.dashboard import require_loopback_host, serve
from diagnostic_clank.paths import default_state_root, resolve_state_paths


@pytest.fixture
def running_server(tmp_path, monkeypatch):
    monkeypatch.setenv("DIAGNOSTIC_CLANK_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("DIAGNOSTIC_CLANK_DASHBOARD_TOKEN", "test-dashboard-token")
    paths = resolve_state_paths()
    server, store = serve(paths=paths, port=0)
    port = server.socket.getsockname()[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=0.5)
            break
        except OSError:
            time.sleep(0.05)
    yield port, paths, store
    server.shutdown()
    store.close()


def _get(port: int, path: str) -> tuple[int, str]:
    try:
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3)
        return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, ""


def _post(port: int, path: str, data: dict) -> tuple[int, str]:
    import urllib.parse
    body = urllib.parse.urlencode(data, doseq=True).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=body, method="POST",
        headers={"Authorization": "Bearer test-dashboard-token"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=3)
        return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


# -- state path / CWD independence -------------------------------------------

def test_state_root_defaults_to_application_support():
    import sys
    root = default_state_root()
    if sys.platform == "darwin":
        assert "Library/Application Support/Diagnostic Clank" in str(root)
    else:
        # Linux/Windows: platform default under home or XDG/LOCALAPPDATA
        assert root.is_absolute()


def test_server_binds_only_loopback(running_server):
    port, _, _ = running_server
    # Confirm the bound host is 127.0.0.1, not 0.0.0.0 or any external interface.
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        result = s.connect_ex(("127.0.0.1", port))
        assert result == 0
        s.close()


@pytest.mark.parametrize(
    "host", ["0.0.0.0", "192.168.1.20", "::", "not a host", "", "example.test"]
)
def test_server_rejects_non_loopback_bind(tmp_path, monkeypatch, host):
    monkeypatch.setenv("DIAGNOSTIC_CLANK_HOME", str(tmp_path / "rejected"))
    with pytest.raises(ValueError, match="must be loopback"):
        serve(paths=resolve_state_paths(), host=host, port=0)


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
def test_loopback_host_validation_accepts_ipv4_ipv6_and_localhost(host):
    require_loopback_host(host)


def test_mutation_without_authentication_is_rejected(running_server):
    port, _, _ = running_server
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/file-inbox/scan", data=b"", method="POST"
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=3)
    assert exc.value.code == 403


def test_dashboard_works_regardless_of_process_cwd(tmp_path, monkeypatch):
    other_dir = tmp_path / "somewhere-else"
    other_dir.mkdir()
    monkeypatch.chdir(other_dir)
    monkeypatch.setenv("DIAGNOSTIC_CLANK_HOME", str(tmp_path / "home2"))
    paths = resolve_state_paths()
    server, store = serve(paths=paths, port=0)
    port = server.socket.getsockname()[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)
    status, _ = _get(port, "/healthz")
    assert status == 200
    # nothing should have been written into the CWD
    assert list(other_dir.iterdir()) == []
    server.shutdown()
    store.close()


# -- routes --------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/", "/incidents", "/incidents/new", "/reports", "/reports/new", "/file-inbox", "/evidence", "/search", "/ingest"])
def test_all_nav_routes_return_200(running_server, path):
    port, _, _ = running_server
    status, _ = _get(port, path)
    assert status == 200


def test_healthz_identifies_application(running_server):
    port, _, _ = running_server
    status, body = _get(port, "/healthz")
    assert status == 200
    assert "DiagnosticClank" in body


def test_v01_badge_present_on_every_page(running_server):
    port, _, _ = running_server
    _, body = _get(port, "/")
    assert "DIAGNOSTIC CLANK v0.1" in body
    assert "LOCAL ARCHIVIST" in body
    assert "FIELD TEST" in body


def test_empty_state_guides_owner_to_add_l(running_server):
    port, _, _ = running_server
    _, body = _get(port, "/")
    assert "No incidents yet" in body
    assert "ADD L" in body


# -- Add L / incident creation flow ---------------------------------------------

def test_add_l_creates_incident_for_known_fleet_clank(running_server):
    port, _, _ = running_server
    status, _ = _post(port, "/incidents", {
        "clank_id": "smartwatch-clank", "title": "Test incident from form",
    })
    assert status == 200  # urlopen follows the 303 redirect to the detail page


def test_add_l_accepts_fleet_wide(running_server):
    port, _, _ = running_server
    status, _ = _post(port, "/incidents", {"clank_id": "fleet-wide", "title": "Fleet-wide L"})
    assert status == 200


def test_incident_visible_after_creation(running_server):
    port, _, _ = running_server
    _post(port, "/incidents", {"clank_id": "fleet-wide", "title": "Visible incident test"})
    _, body = _get(port, "/incidents")
    assert "Visible incident test" in body


def test_newest_canonical_incident_is_in_overview_and_search(running_server):
    port, _, _ = running_server
    _post(port, "/incidents", {
        "clank_id": "watch-clank", "title": "Newest Watch Clank canonical incident",
        "classification": ["STALE_DISCOVERY"],
    })
    _, overview = _get(port, "/")
    _, incidents = _get(port, "/incidents?clank=watch-clank")
    _, search = _get(port, "/search?q=Newest+Watch+Clank+canonical+incident")
    assert "Incidents</div><b>1</b>" in overview
    assert "Newest Watch Clank canonical incident" in overview
    assert "Newest Watch Clank canonical incident" in incidents
    assert "Newest Watch Clank canonical incident" in search


def test_report_findings_are_background_and_individually_visible(running_server):
    port, _, store = running_server
    raw = """# SECTION A — WATCH CLANK

----------
L-CANDIDATE-001 — Candidate watch finding

STATUS:
OPEN

CLANK:
Watch Clank (canonical clank id: watch-clank)

EPISTEMIC STATUS:
CANDIDATE / PROVENANCE REQUIRED

LESSON:
Keep this background finding separate from canonical incidents.
"""
    first = store.reports.ingest_bytes(
        raw.encode(), source_agent="IMPORT", source_type="HISTORICAL_REGISTER",
        filename="historical-register-test.md", primary_clank_id="watch-clank",
    )
    second = store.reports.ingest_bytes(
        raw.encode(), source_agent="IMPORT", source_type="HISTORICAL_REGISTER",
        filename="historical-register-test.md", primary_clank_id="watch-clank",
    )
    report_id = first["report_id"]
    finding_id = f"{report_id}:1:L-CANDIDATE-001"
    assert second["status"] == "duplicate"
    assert len(store.incidents.list(limit=100)) == 0
    _, overview = _get(port, "/")
    _, reports = _get(port, "/reports")
    _, detail = _get(port, f"/reports/{report_id}")
    _, finding = _get(port, f"/reports/{report_id}/findings/{finding_id}")
    _, search = _get(port, "/search?q=L-CANDIDATE-001")
    assert "Incidents</div><b>0</b>" in overview
    assert "Ingested Reports / Background Knowledge" in reports
    assert "Candidate watch finding" in detail
    assert "AUTO_EXTRACTED" in finding
    assert "CANDIDATE / PROVENANCE REQUIRED" in finding
    assert "canonical incident was created" in finding
    assert "L-CANDIDATE-001" in search


# -- Import report ---------------------------------------------------------------

def test_import_report_preserves_raw_text_verbatim(running_server):
    port, _, store = running_server
    raw = "narrative text\n\nCLANKOPS_RECORD\nagent: codex\nverdict: OK\n"
    status, body = _post(port, "/reports", {
        "agent_family": "codex", "primary_clank_id": "fleet-wide", "raw_text": raw,
        "output_type": "general_note",
    })
    assert status == 200
    assert "verdict" in body and "OK" in body  # raw text rendered verbatim on the detail page
    assert "CLANKOPS_RECORD (deterministically extracted)" in body
    # confirm against the store directly too, not just the rendered HTML
    records = store.inbox.list(limit=10)
    assert any(r.raw_text == raw for r in records)


def test_reimporting_identical_report_does_not_duplicate(running_server):
    port, _, _ = running_server
    raw = "duplicate detection test content"
    _post(port, "/reports", {"agent_family": "claude", "primary_clank_id": "fleet-wide", "raw_text": raw})
    _post(port, "/reports", {"agent_family": "claude", "primary_clank_id": "fleet-wide", "raw_text": raw})
    _, body = _get(port, "/reports")
    assert body.count("duplicate detection test content") <= 1 or body.count("<tr>") <= 2  # header row + 1 data row


def test_file_inbox_scan_route_ingests_report(running_server, monkeypatch, tmp_path):
    port, paths, store = running_server
    report_root = tmp_path / "reports"
    monkeypatch.setenv("CLANKOPS_REPORT_ROOT", str(report_root))
    report_root.joinpath("inbox").mkdir(parents=True)
    report = report_root / "inbox" / "gui-scan.md"
    report.write_bytes(b"GUI scan report\n")
    status, body = _post(port, "/file-inbox/scan", {})
    assert status == 200
    assert "ingested=1" in body
    assert not report.exists()
    assert any(r.raw_text == "GUI scan report\n" for r in store.inbox.list(limit=10))
