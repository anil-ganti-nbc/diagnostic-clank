"""Regression tests for the native macOS launcher process lifecycle and the
central mac-launchers symlink -- run in source mode (subprocess of
launcher.py), not the packaged .app. Packaged-app behavior is covered by
the acceptance drill / three clean build cycles, not by pytest.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = REPO_ROOT / "native" / "macos" / "launcher.py"
RUNTIME_PATH = REPO_ROOT.parents[1] / "clank-runtime" / "src"
CENTRAL_LAUNCHER = Path("/Users/anilganti/Clank base/mac-launchers/Diagnostic Clank.app")
CANONICAL_APP = REPO_ROOT / "native" / "macos" / "dist" / "Diagnostic Clank.app"


def _launch(home: Path) -> subprocess.Popen:
    env = dict(os.environ)
    env["DIAGNOSTIC_CLANK_HOME"] = str(home)
    env["DIAGNOSTIC_CLANK_NO_BROWSER"] = "1"
    env["PYTHONPATH"] = f"{RUNTIME_PATH}:{REPO_ROOT / 'src'}"
    return subprocess.Popen([sys.executable, str(LAUNCHER)], env=env)


def _wait_for_marker(home: Path, timeout: float = 10.0) -> dict | None:
    marker = home / "runtime" / "dashboard.json"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if marker.exists():
            try:
                return json.loads(marker.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        time.sleep(0.1)
    return None


def test_launcher_becomes_ready_and_shuts_down_cleanly(tmp_path):
    home = tmp_path / "dc-home"
    proc = _launch(home)
    try:
        info = _wait_for_marker(home)
        assert info is not None, "launcher never became ready (no runtime marker written)"
        assert info["pid"] == proc.pid
        port = info["port"]

        import urllib.request
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=3) as resp:
            assert resp.status == 200

        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=10)
        assert proc.returncode == 0

        assert not (home / "runtime" / "dashboard.json").exists(), "runtime marker not cleaned up on shutdown"

        # port must be released -- a fresh bind should succeed. SO_REUSEADDR
        # matches what HTTPServer itself sets; without it a properly-closed
        # socket can still be in TCP TIME_WAIT and this check would produce
        # a false failure unrelated to whether the app actually released it.
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", port))
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


def test_launcher_state_lives_under_application_support_style_home(tmp_path):
    home = tmp_path / "dc-home-2"
    proc = _launch(home)
    try:
        info = _wait_for_marker(home)
        assert info is not None
        assert (home / "diagnostic.db").exists()
        assert (home / "evidence").is_dir()
        assert (home / "attachments").is_dir()
        assert (home / "quarantine").is_dir()
        # nothing written into the repo itself
        assert not (REPO_ROOT / "diagnostic.db").exists()
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_launcher_becomes_thin_browser_launcher_when_nas_configured(tmp_path):
    """When a canonical NAS instance is configured, the launcher must not
    start a second, independently-writable local server/DB -- no runtime
    marker should ever appear, and the process should exit promptly."""
    home = tmp_path / "dc-home-nas-configured"
    env = dict(os.environ)
    env["DIAGNOSTIC_CLANK_HOME"] = str(home)
    env["DIAGNOSTIC_CLANK_NO_BROWSER"] = "1"
    env["DIAGNOSTIC_CLANK_NAS_URL"] = "http://192.0.2.1:8420/"  # TEST-NET-1, never dialed
    env["PYTHONPATH"] = f"{RUNTIME_PATH}:{REPO_ROOT / 'src'}"
    proc = subprocess.Popen([sys.executable, str(LAUNCHER)], env=env)
    try:
        proc.wait(timeout=10)
        assert proc.returncode == 0
        assert not (home / "runtime" / "dashboard.json").exists()
        assert not (home / "diagnostic.db").exists()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


@pytest.mark.skipif(not CENTRAL_LAUNCHER.exists(), reason="central launcher symlink not yet created on this machine")
def test_central_launcher_is_a_symlink_not_a_copy():
    assert CENTRAL_LAUNCHER.is_symlink()


@pytest.mark.skipif(not CENTRAL_LAUNCHER.exists(), reason="central launcher symlink not yet created on this machine")
def test_central_launcher_resolves_to_canonical_app():
    resolved = CENTRAL_LAUNCHER.resolve()
    assert resolved == CANONICAL_APP.resolve()
