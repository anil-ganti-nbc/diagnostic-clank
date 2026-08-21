from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPOSITORY_ROOT / "operations" / "phase0" / "preflight.py"


def test_preflight_records_unknowns_without_mutating_target(tmp_path):
    evidence = tmp_path / "preflight.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--target-type",
            "HETZNER",
            "--instance-id",
            "phase0-test-instance",
            "--repository-path",
            str(REPOSITORY_ROOT),
            "--evidence-out",
            str(evidence),
            "--inspect-path",
            f"database={tmp_path}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2  # incomplete evidence never closes the gate
    data = json.loads(evidence.read_text(encoding="utf-8"))
    assert data["target_type"] == "HETZNER"
    assert data["mutation_performed"] is False
    assert data["scheduler"].startswith("UNKNOWN")
    assert data["backup_restore"] == "UNKNOWN"


def test_preflight_refuses_relative_paths_and_existing_output(tmp_path):
    existing = tmp_path / "existing.json"
    existing.write_text("preserve me", encoding="utf-8")

    for repository, output in (("relative/repository", tmp_path / "new.json"), (str(REPOSITORY_ROOT), existing)):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--target-type",
                "NAS",
                "--instance-id",
                "phase0-test-instance",
                "--repository-path",
                repository,
                "--evidence-out",
                str(output),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 2

    assert existing.read_text(encoding="utf-8") == "preserve me"
