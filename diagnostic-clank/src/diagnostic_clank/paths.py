"""Application Support state path resolution -- CWD-independent.

All mutable Diagnostic Clank state lives under
~/Library/Application Support/Diagnostic Clank/ regardless of how the
process was launched or what its current working directory is. Nothing
here ever writes into the repository, the .app bundle, the launch CWD, or
a PyInstaller temp extraction directory.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "Diagnostic Clank"


def default_state_root() -> Path:
    return Path.home() / "Library" / "Application Support" / APP_NAME


@dataclass(frozen=True)
class StatePaths:
    home: Path
    db_path: Path
    evidence_dir: Path
    attachments_dir: Path
    quarantine_dir: Path
    log_dir: Path
    runtime_dir: Path

    @property
    def runtime_marker(self) -> Path:
        return self.runtime_dir / "dashboard.json"


def resolve_state_paths(override_home: str | Path | None = None) -> StatePaths:
    """override_home / DIAGNOSTIC_CLANK_HOME env var take precedence over
    the default Application Support location -- used by tests and by the
    field-test launcher's isolation, never by normal Finder launch."""
    home_value = override_home or os.environ.get("DIAGNOSTIC_CLANK_HOME")
    home = Path(home_value).expanduser().resolve() if home_value else default_state_root()
    paths = StatePaths(
        home=home,
        db_path=home / "diagnostic.db",
        evidence_dir=home / "evidence",
        attachments_dir=home / "attachments",
        quarantine_dir=home / "quarantine",
        log_dir=home / "logs",
        runtime_dir=home / "runtime",
    )
    for d in (paths.home, paths.evidence_dir, paths.attachments_dir, paths.quarantine_dir,
              paths.log_dir, paths.runtime_dir):
        d.mkdir(parents=True, exist_ok=True)
    return paths
