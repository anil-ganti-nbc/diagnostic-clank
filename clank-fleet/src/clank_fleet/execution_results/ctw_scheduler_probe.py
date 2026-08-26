"""Cron log scheduler-fire probe for CTW.

Reads existing cron log files (written by the OS cron daemon, NOT by
Motherclank) and extracts positive fire evidence. Strictly read-only.

The CTW crontab redirects output to a per-day log file:
    >> logs/cron-$(date -u +\%Y\%m\%d).log

Each successful shell invocation produces a timestamped line. The probe
matches lines against the expected invocation target to produce canonical
scheduler traces.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from motherclank.scheduler_traces import make_trace

CRON_LOG_LINE_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}T[\d:]+Z?)\s+"
    r"(?P<content>.*)"
)


def extract_cron_fires(
    *,
    clank_id: str,
    instance_id: str,
    lane_id: str,
    log_dir: Path,
    expected_target: str,
    since: str | None = None,
) -> list[dict[str, Any]]:
    """Scan cron log files for positively observed invocations.

    A fire is POSITIVE when the expected target string appears in the log.
    This is not inference — it is pattern matching against the participant's
    own documented invocation path.
    """
    if not log_dir.exists():
        return []

    traces = []
    for log_file in sorted(log_dir.glob("cron-*.log")):
        try:
            content = log_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in content.splitlines():
            if expected_target not in line:
                continue
            # Extract or construct a timestamp from the log line context
            ts_match = re.search(
                r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2})", line)
            fired_at = ts_match.group(1).replace(" ", "T") + "Z" \
                if ts_match else None
            if since and fired_at and fired_at < since:
                continue
            traces.append(make_trace(
                trace_id=f"cron-{clank_id}-{len(traces)}",
                clank_id=clank_id,
                instance_id=instance_id,
                lane_id=lane_id,
                scheduler_type="cron",
                unit_or_job=expected_target,
                invoked_at=fired_at,
                process_started=None,
                evidence_source="journal",
                notes=f"matched '{expected_target}' in {log_file.name}",
            ))
    return traces
