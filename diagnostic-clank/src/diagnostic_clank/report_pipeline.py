"""Local ClankOps report file pipeline — portable, path-identity free.

Flow:
  CLANKOPS_REPORT_INBOX/*.md
    → content hash
    → dedup against knowledge store
    → preserve exact raw text as Agent Report
    → parse CLANKOPS_RECORD if present
    → move source file to processed/ or quarantine/

Never mutates report body. Never invents structured fields.
Absolute source path is provenance only, not identity.
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from clank_runtime.knowledge.clankops_record import CLANKOPSRecord, extract_clankops_record
from clank_runtime.knowledge.inbox import AgentFamily, OutputType, text_hash
from clank_runtime.knowledge.store import DiagnosticKnowledgeStore, IngestResult
from clank_runtime.registry.core import ClankRegistration

from diagnostic_clank.paths import ReportPaths, resolve_report_paths, resolve_state_paths
from diagnostic_clank.paths import StatePaths

# Safety limits
MAX_REPORT_BYTES = 2 * 1024 * 1024  # 2 MiB
_SAFE_NAME = re.compile(r"^[A-Za-z0-9._\- ]+\.(md|markdown|txt)$", re.IGNORECASE)


@dataclass
class FileIngestOutcome:
    source_filename: str
    content_hash: str | None = None
    status: str = "pending"  # ingested | duplicate | quarantined | skipped
    output_id: str | None = None
    was_duplicate: bool = False
    quarantine_reason: str | None = None
    clankops: CLANKOPSRecord | None = None
    detail: str = ""


@dataclass
class ScanResult:
    scanned: int = 0
    ingested: int = 0
    duplicates: int = 0
    quarantined: int = 0
    outcomes: list[FileIngestOutcome] = field(default_factory=list)


def _infer_agent_family(name: str, record: CLANKOPSRecord) -> AgentFamily:
    hint = (record.agent or name or "").lower()
    if "claude" in hint:
        return AgentFamily.CLAUDE
    if "codex" in hint:
        return AgentFamily.CODEX
    if "grok" in hint:
        return AgentFamily.GROK
    return AgentFamily.MISC


def _infer_project(name: str, record: CLANKOPSRecord) -> str:
    if record.project and record.project.strip():
        slug = record.project.strip().lower().replace(" ", "-")
        return slug
    # filename: YYYYMMDD-HHMMSS_<agent>_<project>_<task>.md
    parts = Path(name).stem.split("_")
    if len(parts) >= 3:
        return parts[2].lower()
    return "fleet-wide"


def _unique_dest(dir_path: Path, filename: str) -> Path:
    dest = dir_path / filename
    if not dest.exists():
        return dest
    stem, suffix = Path(filename).stem, Path(filename).suffix
    for i in range(1, 1000):
        candidate = dir_path / f"{stem}__{i}{suffix}"
        if not candidate.exists():
            return candidate
    return dir_path / f"{stem}__{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}{suffix}"


def scan_and_ingest(
    store: DiagnosticKnowledgeStore,
    report_paths: ReportPaths | None = None,
    *,
    max_bytes: int = MAX_REPORT_BYTES,
) -> ScanResult:
    """Scan inbox, ingest new Markdown reports, move files after success."""
    report_paths = report_paths or resolve_report_paths()
    report_paths.ensure()
    result = ScanResult()

    entries = sorted(report_paths.inbox.iterdir()) if report_paths.inbox.is_dir() else []
    for path in entries:
        if not path.is_file():
            continue
        result.scanned += 1
        outcome = _ingest_one(store, report_paths, path, max_bytes=max_bytes)
        result.outcomes.append(outcome)
        if outcome.status == "ingested":
            result.ingested += 1
        elif outcome.status == "duplicate":
            result.duplicates += 1
        elif outcome.status == "quarantined":
            result.quarantined += 1
    return result


def _ingest_one(
    store: DiagnosticKnowledgeStore,
    report_paths: ReportPaths,
    path: Path,
    *,
    max_bytes: int,
) -> FileIngestOutcome:
    name = path.name
    outcome = FileIngestOutcome(source_filename=name)

    if not _SAFE_NAME.match(name):
        return _quarantine(report_paths, path, outcome, "unsupported_filename")

    try:
        size = path.stat().st_size
    except OSError as exc:
        return _quarantine(report_paths, path, outcome, f"unreadable:{exc}")

    if size > max_bytes:
        return _quarantine(report_paths, path, outcome, f"oversized:{size}")

    try:
        raw_bytes = path.read_bytes()
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            raw_text = path.read_bytes().decode("utf-8", errors="replace")
            # still preserve bytes identity via hash of original
            raw_bytes = path.read_bytes()
        except OSError as exc:
            return _quarantine(report_paths, path, outcome, f"unreadable:{exc}")
    except OSError as exc:
        return _quarantine(report_paths, path, outcome, f"unreadable:{exc}")

    if not raw_text.strip():
        return _quarantine(report_paths, path, outcome, "empty_body")

    digest = text_hash(raw_text)
    outcome.content_hash = digest
    clankops = extract_clankops_record(raw_text)
    outcome.clankops = clankops

    agent_family = _infer_agent_family(name, clankops)
    project = _infer_project(name, clankops)
    if project != "fleet-wide" and store.registry.get(project) is None:
        store.registry.register(ClankRegistration(clank_id=project, display_name=project))

    # session_label carries original filename + optional host path as provenance only
    session = f"file:{name}"

    try:
        ingest: IngestResult = store.ingest_report(
            agent_family=agent_family,
            primary_clank_id=project,
            raw_text=raw_text,
            output_type=OutputType.HANDOFF,
            session_label=session,
        )
    except Exception as exc:  # noqa: BLE001 — quarantine without poisoning store
        return _quarantine(report_paths, path, outcome, f"ingest_error:{exc}")

    outcome.output_id = ingest.output.output_id
    outcome.was_duplicate = ingest.was_duplicate
    outcome.status = "duplicate" if ingest.was_duplicate else "ingested"
    outcome.detail = f"hash={digest[:12]} output_id={ingest.output.output_id[:8]}"

    # Move source after successful canonical preserve (including deduped)
    try:
        dest = _unique_dest(report_paths.processed, name)
        shutil.move(str(path), str(dest))
    except OSError as exc:
        outcome.detail += f" move_failed:{exc}"
    return outcome


def _quarantine(
    report_paths: ReportPaths,
    path: Path,
    outcome: FileIngestOutcome,
    reason: str,
) -> FileIngestOutcome:
    outcome.status = "quarantined"
    outcome.quarantine_reason = reason
    try:
        dest = _unique_dest(report_paths.quarantine, path.name)
        if path.exists():
            shutil.move(str(path), str(dest))
        # sidecar reason
        (dest.with_suffix(dest.suffix + ".reason.txt")).write_text(reason + "\n", encoding="utf-8")
    except OSError as exc:
        outcome.detail = f"quarantine_move_failed:{exc}"
    return outcome


def submit_report_text(
    body: str,
    *,
    agent: str,
    project: str,
    task: str,
    report_paths: ReportPaths | None = None,
    extra_footer: str | None = None,
) -> Path:
    """Write a new unique report into the resolved inbox (dogfood / agents)."""
    report_paths = report_paths or resolve_report_paths()
    report_paths.ensure()
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    agent_slug = re.sub(r"[^a-z0-9-]", "-", agent.lower()).strip("-") or "agent"
    project_slug = re.sub(r"[^a-z0-9-]", "-", project.lower()).strip("-") or "project"
    task_slug = re.sub(r"[^a-z0-9-]", "-", task.lower()).strip("-") or "task"
    filename = f"{ts}_{agent_slug}_{project_slug}_{task_slug}.md"
    dest = report_paths.inbox / filename
    if dest.exists():
        dest = _unique_dest(report_paths.inbox, filename)
    text = body.rstrip() + "\n"
    if extra_footer:
        text += "\n" + extra_footer.rstrip() + "\n"
    dest.write_text(text, encoding="utf-8")
    return dest


def open_store(
    state: StatePaths | None = None,
) -> tuple[DiagnosticKnowledgeStore, StatePaths]:
    state = state or resolve_state_paths()
    store = DiagnosticKnowledgeStore(
        db_path=state.db_path,
        evidence_dir=state.evidence_dir,
        quarantine_dir=state.quarantine_dir,
    )
    return store, state
