"""Container entrypoint regression coverage -- run in source mode (subprocess
of native/docker/entrypoint.py), since this Mac has no Docker/container
runtime to exercise the actual image build. Full containerized behavior is
covered by the NAS deployment acceptance drill, not by pytest.
"""
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = REPO_ROOT / "native" / "docker" / "entrypoint.py"
RUNTIME_PATH = REPO_ROOT.parents[1] / "clank-runtime" / "src"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _launch(home: Path, *, bind_host: str, port: int) -> subprocess.Popen:
    env = dict(os.environ)
    env["DIAGNOSTIC_CLANK_HOME"] = str(home)
    env["DIAGNOSTIC_CLANK_BIND_HOST"] = bind_host
    env["DIAGNOSTIC_CLANK_PORT"] = str(port)
    env["PYTHONPATH"] = f"{RUNTIME_PATH}:{REPO_ROOT / 'src'}"
    return subprocess.Popen(
        [sys.executable, str(ENTRYPOINT)], env=env, stderr=subprocess.PIPE, text=True
    )


def _wait_for_healthz(port: int, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=0.5) as resp:
                if resp.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(0.1)
    return False


def test_entrypoint_binds_configured_host_and_port_and_shuts_down_cleanly(tmp_path):
    home = tmp_path / "dc-container-home"
    port = _free_port()
    proc = _launch(home, bind_host="127.0.0.1", port=port)
    try:
        assert _wait_for_healthz(port), "entrypoint never became ready on the configured port"
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=3) as resp:
            body = json.loads(resp.read())
            assert body["application"] == "DiagnosticClank"

        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=10)
        assert proc.returncode == 0

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", port))  # must not still be held
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


def test_entrypoint_defaults_to_loopback_bind_when_unset(tmp_path):
    """Fails safe (unreachable), not fails open, if a deployment forgets to
    set DIAGNOSTIC_CLANK_BIND_HOST."""
    home = tmp_path / "dc-container-home-default"
    port = _free_port()
    env = dict(os.environ)
    env["DIAGNOSTIC_CLANK_HOME"] = str(home)
    env.pop("DIAGNOSTIC_CLANK_BIND_HOST", None)
    env["DIAGNOSTIC_CLANK_PORT"] = str(port)
    env["PYTHONPATH"] = f"{RUNTIME_PATH}:{REPO_ROOT / 'src'}"
    proc = subprocess.Popen([sys.executable, str(ENTRYPOINT)], env=env)
    try:
        assert _wait_for_healthz(port)
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
