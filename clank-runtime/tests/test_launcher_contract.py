"""Launcher contract — one shared preflight, three thin platform wrappers."""
from __future__ import annotations
import os, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DC = REPO / "diagnostic-clank"
PREFLIGHT = DC / "launcher" / "common" / "preflight.py"
LINUX = DC / "launcher" / "linux" / "launch.sh"
MACOS = DC / "launcher" / "macos" / "launch.command"
WIN = DC / "launcher" / "windows" / "launch.ps1"

def _env(home: Path) -> dict:
    env = os.environ.copy()
    env["DIAGNOSTIC_CLANK_HOME"] = str(home)
    env["PYTHONPATH"] = f"{REPO / 'clank-runtime' / 'src'}:{REPO / 'clank-desktop' / 'src'}:{env.get('PYTHONPATH','')}"
    env["DIAGNOSTIC_MODE"] = "preflight"
    return env

def test_launcher_files_exist():
    assert PREFLIGHT.is_file()
    assert LINUX.is_file() and os.access(LINUX, os.X_OK)
    assert MACOS.is_file() and os.access(MACOS, os.X_OK)
    assert WIN.is_file()

def test_common_preflight_ok(tmp_path: Path):
    home = tmp_path / "dc"; home.mkdir()
    proc = subprocess.run([sys.executable, str(PREFLIGHT), "preflight"], env=_env(home),
                          capture_output=True, text=True, cwd=str(REPO))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "overall: OK" in proc.stdout

def test_linux_wrapper_preflight(tmp_path: Path):
    home = tmp_path / "dc"; home.mkdir()
    proc = subprocess.run(["bash", str(LINUX), "preflight"], env=_env(home),
                          capture_output=True, text=True, cwd=str(REPO))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "overall: OK" in proc.stdout

def test_macos_wrapper_same_contract(tmp_path: Path):
    home = tmp_path / "dc"; home.mkdir()
    proc = subprocess.run(["bash", str(MACOS), "preflight"], env=_env(home),
                          capture_output=True, text=True, cwd=str(REPO))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "overall: OK" in proc.stdout

def test_wrappers_invoke_same_preflight():
    for path in (LINUX, MACOS):
        text = path.read_text()
        assert "preflight.py" in text and "DIAGNOSTIC_CLANK_HOME" in text
    assert "preflight.py" in WIN.read_text()

def test_contract_version_stable():
    assert 'CONTRACT_VERSION = "1.0.0"' in PREFLIGHT.read_text()
