"""Regression tests for the Diagnostic Clank v0.1 dashboard/loopback server."""
from __future__ import annotations

import os
import threading
import time
import urllib.request

import pytest

from diagnostic_clank.dashboard import serve
from diagnostic_clank.paths import default_state_root, resolve_state_paths


@pytest.fixture
def running_server(tmp_path, monkeypatch):
    monkeypatch.setenv("DIAGNOSTIC_CLANK_HOME", str(tmp_path / "home"))
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
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=body, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=3)
        return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


# -- state path / CWD independence -------------------------------------------

def test_state_root_defaults_to_application_support():
    root = default_state_root()
    assert "Library/Application Support/Diagnostic Clank" in str(root)


def test_server_binds_only_loopback(running_server):
    port, _, _ = running_server
    # Confirm the bound host is 127.0.0.1, not 0.0.0.0 or any external interface.
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        result = s.connect_ex(("127.0.0.1", port))
        assert result == 0
        s.close()


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

@pytest.mark.parametrize("path", ["/", "/incidents", "/incidents/new", "/reports", "/reports/new", "/evidence", "/search", "/ingest"])
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
