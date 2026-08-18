"""diagnostic-clank CLI — paths / report submit / inbox scan."""
from __future__ import annotations

import argparse
import json
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

    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
