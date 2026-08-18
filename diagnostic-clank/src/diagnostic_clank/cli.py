"""diagnostic-clank CLI — paths / report submit / inbox scan."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path


def cmd_paths(_: argparse.Namespace) -> int:
    from diagnostic_clank.paths import resolved_paths_summary

    print(json.dumps(resolved_paths_summary(), indent=2))
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    from diagnostic_clank.paths import resolve_report_paths, resolve_state_paths
    from diagnostic_clank.report_pipeline import open_store, scan_and_ingest

    state = resolve_state_paths(args.data_dir)
    reports = resolve_report_paths(args.report_root)
    store, _ = open_store(state)
    try:
        result = scan_and_ingest(store, reports)
    finally:
        store.close()
    print(
        json.dumps(
            {
                "scanned": result.scanned,
                "ingested": result.ingested,
                "duplicates": result.duplicates,
                "quarantined": result.quarantined,
                "inbox": str(reports.inbox),
                "outcomes": [
                    {
                        "file": o.source_filename,
                        "status": o.status,
                        "hash": o.content_hash,
                        "output_id": o.output_id,
                        "reason": o.quarantine_reason,
                    }
                    for o in result.outcomes
                ],
            },
            indent=2,
        )
    )
    return 0


def cmd_submit(args: argparse.Namespace) -> int:
    from diagnostic_clank.paths import resolve_report_paths
    from diagnostic_clank.report_pipeline import submit_report_text

    src = Path(args.file) if args.file else None
    if src is not None:
        body = src.read_text(encoding="utf-8")
    elif args.stdin:
        body = sys.stdin.read()
    else:
        print("provide --file or --stdin", file=sys.stderr)
        return 2

    footer = None
    if args.append_record:
        footer = _build_record(
            agent=args.agent,
            project=args.project,
            task=args.task,
            verdict=args.verdict,
        )
    reports = resolve_report_paths(args.report_root)
    dest = submit_report_text(
        body,
        agent=args.agent,
        project=args.project,
        task=args.task,
        report_paths=reports,
        extra_footer=footer,
    )
    print(json.dumps({"written": str(dest), "inbox": str(reports.inbox)}, indent=2))
    return 0


def cmd_identity(_: argparse.Namespace) -> int:
    """Provenance claim for a running instance -- never trust a checkout or
    tag alone. Deliberately reports 'unknown' rather than guessing when
    DIAGNOSTIC_CLANK_SOURCE_REVISION wasn't baked in at build time (see
    native/docker: GIT_REVISION build-arg -> this env var -> this command)."""
    revision = os.environ.get("DIAGNOSTIC_CLANK_SOURCE_REVISION", "unknown")
    print(
        json.dumps(
            {
                "application": "DiagnosticClank",
                "source_revision": revision,
                "source_revision_short": revision[:12] if revision != "unknown" else "unknown",
            },
            indent=2,
        )
    )
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    from diagnostic_clank.backup import create_backup
    from diagnostic_clank.paths import discover_repo_root, resolve_state_paths

    state = resolve_state_paths(args.data_dir)
    revision = args.revision
    if revision is None:
        repo = discover_repo_root()
        if repo is not None:
            try:
                import subprocess

                revision = subprocess.run(
                    ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, timeout=5
                ).stdout.strip() or None
            except Exception:  # noqa: BLE001 -- revision is best-effort metadata only
                revision = None
    manifest = create_backup(state, Path(args.dest), source_repo_revision=revision)
    print(manifest.to_json())
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    from diagnostic_clank.backup import restore_backup

    dest = restore_backup(Path(args.backup_dir), Path(args.dest))
    print(json.dumps({"restored_to": str(dest.home), "db_path": str(dest.db_path)}, indent=2))
    return 0


def _build_record(*, agent: str, project: str, task: str, verdict: str | None) -> str:
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "CLANKOPS_RECORD",
        "schema_version: 1",
        f"agent: {agent}",
        f"project: {project}",
        f"task: {task}",
        f"timestamp: {ts}",
        "repo: ",
        "branch: ",
        "start_sha: ",
        "end_sha: ",
        "pr: ",
        "hosts_read: ",
        "hosts_modified: ",
        "tests: ",
        "p0: ",
        "p1: ",
        "p2: ",
        "p3: ",
        "decisions: ",
        "unresolved: ",
        "next_action: ",
        f"verdict: {verdict or ''}",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="diagnostic-clank", description="Diagnostic Clank v0.1 tools")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_paths = sub.add_parser("paths", help="Show resolved logical→physical paths")
    p_paths.set_defaults(func=cmd_paths)

    p_scan = sub.add_parser("scan-inbox", help="Scan CLANKOPS_REPORT_INBOX and ingest")
    p_scan.add_argument("--data-dir", default=None, help="Override DIAGNOSTIC_DATA_DIR")
    p_scan.add_argument("--report-root", default=None, help="Override CLANKOPS_REPORT_ROOT")
    p_scan.set_defaults(func=cmd_scan)

    p_sub = sub.add_parser("report", help="Report helpers")
    report_sub = p_sub.add_subparsers(dest="report_cmd", required=True)
    p_submit = report_sub.add_parser("submit", help="Write a report into the resolved inbox")
    p_submit.add_argument("--file", default=None)
    p_submit.add_argument("--stdin", action="store_true")
    p_submit.add_argument("--agent", default="grok")
    p_submit.add_argument("--project", default="diagnostic-clank")
    p_submit.add_argument("--task", default="task")
    p_submit.add_argument("--verdict", default=None)
    p_submit.add_argument("--append-record", action="store_true")
    p_submit.add_argument("--report-root", default=None)
    p_submit.set_defaults(func=cmd_submit)

    p_backup = sub.add_parser("backup", help="Application-consistent backup of the local knowledge state")
    p_backup.add_argument("dest", help="Destination directory for the backup (created if missing)")
    p_backup.add_argument("--data-dir", default=None, help="Override DIAGNOSTIC_DATA_DIR")
    p_backup.add_argument("--revision", default=None, help="Override recorded source repo revision")
    p_backup.set_defaults(func=cmd_backup)

    p_restore = sub.add_parser("restore", help="Restore a backup into an isolated destination")
    p_restore.add_argument("backup_dir", help="Path to a backup directory produced by 'backup'")
    p_restore.add_argument("dest", help="Isolated destination state directory (never the live data dir)")
    p_restore.set_defaults(func=cmd_restore)

    p_identity = sub.add_parser("identity", help="Report the source revision baked into this build")
    p_identity.set_defaults(func=cmd_identity)

    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
