"""Portable path resolution — logical locations, not host-specific constants.

LOGICAL:
  DIAGNOSTIC_DATA_DIR / DIAGNOSTIC_CLANK_HOME
  CLANKOPS_REPORT_ROOT (+ inbox / processed / quarantine)
  DIAGNOSTIC_REPO_ROOT (discovered, never required for identity)

Physical resolution order for each logical root:
  explicit argument → environment override → platform-appropriate default

Host absolute paths are never object identity. Content hash is.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "Diagnostic Clank"
APP_NAME_SLUG = "diagnostic-clank"


def default_state_root() -> Path:
    """Platform-appropriate application data directory."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_NAME
        return Path.home() / "AppData" / "Local" / APP_NAME
    # Linux / other: XDG
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / APP_NAME_SLUG
    return Path.home() / ".local" / "share" / APP_NAME_SLUG


def default_report_root() -> Path:
    """Default CLANKOPS report exchange root (outside Diagnostic DB).

    Co-locates with the *resolved* state root (honoring DIAGNOSTIC_CLANK_HOME
    / DIAGNOSTIC_DATA_DIR if either is set), not unconditionally the
    platform default -- otherwise a container/deployment that overrides the
    state root to a persistent bind mount would silently get a report inbox
    under the ephemeral default instead, with no error anywhere.
    """
    home_value = os.environ.get("DIAGNOSTIC_CLANK_HOME") or os.environ.get("DIAGNOSTIC_DATA_DIR")
    base = Path(home_value).expanduser().resolve() if home_value else default_state_root()
    return base / "clankops-reports"


def discover_repo_root() -> Path | None:
    """Best-effort: walk up from this file looking for pyproject/git."""
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / "pyproject.toml").is_file() and (parent / "src" / "diagnostic_clank").is_dir():
            return parent
        if (parent / ".git").exists() and (parent / "diagnostic-clank").is_dir():
            return parent / "diagnostic-clank"
    return None


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


@dataclass(frozen=True)
class ReportPaths:
    """External exchange directory — source evidence offered for ingestion."""

    root: Path
    inbox: Path
    processed: Path
    quarantine: Path

    def ensure(self) -> None:
        for d in (self.root, self.inbox, self.processed, self.quarantine):
            d.mkdir(parents=True, exist_ok=True)
        readme = self.root / "README.md"
        if not readme.exists():
            readme.write_text(
                "# ClankOps Reports\n\n"
                "inbox/ — drop agent Markdown reports here\n"
                "processed/ — successfully ingested (moved after canonical preserve)\n"
                "quarantine/ — unreadable/malformed/oversized\n\n"
                "Diagnostic's canonical evidence lives in DIAGNOSTIC_DATA_DIR, not here.\n",
                encoding="utf-8",
            )


def resolve_state_paths(override_home: str | Path | None = None) -> StatePaths:
    """override_home / DIAGNOSTIC_CLANK_HOME / DIAGNOSTIC_DATA_DIR take precedence."""
    home_value = (
        override_home
        or os.environ.get("DIAGNOSTIC_CLANK_HOME")
        or os.environ.get("DIAGNOSTIC_DATA_DIR")
    )
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
    for d in (
        paths.home,
        paths.evidence_dir,
        paths.attachments_dir,
        paths.quarantine_dir,
        paths.log_dir,
        paths.runtime_dir,
    ):
        d.mkdir(parents=True, exist_ok=True)
    return paths


def resolve_report_paths(override_root: str | Path | None = None) -> ReportPaths:
    """CLANKOPS_REPORT_ROOT env or argument; else platform default under state root."""
    root_value = override_root or os.environ.get("CLANKOPS_REPORT_ROOT")
    root = Path(root_value).expanduser().resolve() if root_value else default_report_root()
    paths = ReportPaths(
        root=root,
        inbox=root / "inbox",
        processed=root / "processed",
        quarantine=root / "quarantine",
    )
    paths.ensure()
    return paths


def resolved_paths_summary(
    state: StatePaths | None = None,
    reports: ReportPaths | None = None,
) -> dict[str, str]:
    state = state or resolve_state_paths()
    reports = reports or resolve_report_paths()
    repo = discover_repo_root()
    return {
        "DIAGNOSTIC_DATA_DIR": str(state.home),
        "DIAGNOSTIC_DB_PATH": str(state.db_path),
        "CLANKOPS_REPORT_ROOT": str(reports.root),
        "CLANKOPS_REPORT_INBOX": str(reports.inbox),
        "CLANKOPS_REPORT_PROCESSED": str(reports.processed),
        "CLANKOPS_REPORT_QUARANTINE": str(reports.quarantine),
        "DIAGNOSTIC_REPO_ROOT": str(repo) if repo else "",
        "platform": sys.platform,
    }
