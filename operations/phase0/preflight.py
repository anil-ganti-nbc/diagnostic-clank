"""Read-only Phase 0 host preflight evidence collector.

This script deliberately has no mutation or remote-execution mode.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path


SECRET_WORDS = re.compile(r"(?:secret|token|password|credential|webhook|api[_-]?key)", re.I)


def _safe_absolute(value: str, *, must_exist: bool = True) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("path must be absolute")
    resolved = path.resolve()
    if resolved == Path(resolved.anchor):
        raise argparse.ArgumentTypeError("filesystem roots are not valid targets")
    if must_exist and not resolved.exists():
        raise argparse.ArgumentTypeError("path does not exist")
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
        env={"PATH": os.environ.get("PATH", "")},
    )
    return result.stdout.strip()


def _inspect_path(label_and_path: str) -> tuple[str, dict[str, object]]:
    if "=" not in label_and_path:
        raise argparse.ArgumentTypeError("inspect path must be LABEL=/absolute/path")
    label, raw_path = label_and_path.split("=", 1)
    if not label or SECRET_WORDS.search(label):
        raise argparse.ArgumentTypeError("empty or secret-like labels are prohibited")
    path = _safe_absolute(raw_path)
    stat = path.stat()
    evidence: dict[str, object] = {
        "path": str(path),
        "kind": "directory" if path.is_dir() else "file",
        "readable": os.access(path, os.R_OK),
        "writable": os.access(path, os.W_OK),
        "mode": oct(stat.st_mode & 0o777),
        "size_bytes": stat.st_size,
        "modified_utc": dt.datetime.fromtimestamp(stat.st_mtime, dt.UTC).isoformat(),
    }
    if path.is_file():
        evidence["sha256"] = _sha256(path)
    return label, evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect non-secret, read-only host evidence")
    parser.add_argument("--target-type", required=True, choices=("HETZNER", "NAS"))
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--repository-path", required=True, type=_safe_absolute)
    parser.add_argument("--evidence-out", required=True)
    parser.add_argument("--inspect-path", action="append", default=[])
    args = parser.parse_args()

    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,79}", args.instance_id):
        parser.error("instance-id must be an explicit stable lowercase identifier")
    output = _safe_absolute(args.evidence_out, must_exist=False)
    if output.exists():
        parser.error("evidence output already exists; refusing to overwrite")
    if not output.parent.exists():
        parser.error("evidence output parent must already exist")

    repo = args.repository_path
    if not (repo / ".git").exists():
        parser.error("repository-path is not a Git working tree")
    inspected = dict(_inspect_path(item) for item in args.inspect_path)
    lockfiles = {}
    for name in ("uv.lock", "requirements.lock", "requirements.txt", "poetry.lock"):
        candidate = repo / name
        if candidate.is_file():
            lockfiles[name] = {"sha256": _sha256(candidate), "size_bytes": candidate.stat().st_size}

    evidence = {
        "schema_version": 1,
        "mode": "READ_ONLY_PREFLIGHT",
        "target_type": args.target_type,
        "instance_id": args.instance_id,
        "observed_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "host": {"node": platform.node(), "system": platform.system(), "release": platform.release()},
        "repository": {
            "path": str(repo),
            "head_sha": _git(repo, "rev-parse", "HEAD"),
            "branch": _git(repo, "branch", "--show-current") or "DETACHED",
            "status_porcelain": _git(repo, "status", "--porcelain=v1", "--untracked-files=no"),
        },
        "runtime": {"python": sys.version.split()[0], "implementation": platform.python_implementation()},
        "dependency_locks": lockfiles or "UNKNOWN",
        "inspected_paths": inspected or "UNKNOWN",
        "scheduler": "UNKNOWN; export and review separately without secret-bearing command lines",
        "notification_authority": "UNKNOWN",
        "backup_restore": "UNKNOWN",
        "rollback_artifact": "UNKNOWN",
        "mutation_performed": False,
    }
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"read-only preflight recorded: {output}")
    print("result: INVENTORY_INCOMPLETE until operator evidence replaces UNKNOWN fields")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
