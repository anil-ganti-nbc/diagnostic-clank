"""`diagnostic-clank identity` -- provenance reporting for a running build.
Deliberately reports 'unknown' rather than guessing when no source revision
was baked in at build time (see native/docker's GIT_REVISION build-arg).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

CLI = [sys.executable, "-m", "diagnostic_clank.cli"]
REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = REPO_ROOT.parents[1] / "clank-runtime" / "src"


def _run(env_extra: dict[str, str]) -> dict:
    import os

    env = dict(os.environ)
    env["PYTHONPATH"] = f"{RUNTIME_PATH}:{REPO_ROOT / 'src'}"
    env.update(env_extra)
    result = subprocess.run(CLI + ["identity"], capture_output=True, text=True, env=env, check=True)
    return json.loads(result.stdout)


def test_identity_reports_unknown_when_not_baked_in():
    import os

    env = {k: v for k, v in os.environ.items() if k != "DIAGNOSTIC_CLANK_SOURCE_REVISION"}
    result = _run(env)
    assert result["source_revision"] == "unknown"
    assert result["source_revision_short"] == "unknown"


def test_identity_reports_baked_in_revision():
    fake_sha = "a" * 40
    result = _run({"DIAGNOSTIC_CLANK_SOURCE_REVISION": fake_sha})
    assert result["source_revision"] == fake_sha
    assert result["source_revision_short"] == fake_sha[:12]
