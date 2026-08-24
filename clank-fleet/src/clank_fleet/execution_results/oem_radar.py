"""OEM Radar execution-result extractor (P-4.2).

Semantic contract traced from canonical OEM Radar source
(src/oem_radar/cli.py cmd_run + src/oem_radar/core/crawl_service.py +
core/runner.py, verified against the deployed implementation):

1. ``cmd_run`` prints ``done: {out.sources} source(s) crawled,
   {out.snapshots} snapshot(s), {out.events} event(s)`` ONLY after
   ``execute_crawl`` returned normally - i.e., config loaded, the run lock
   was acquired, due-gating executed, every due source was attempted and
   recorded, and the outbox was drained.
2. ``out.sources = len(stats)`` where stats accumulate ONLY for sources
   that were actually run; sources skipped by min_interval due-gating emit
   ``source_skipped`` and are deliberately excluded. Therefore::

        done: 0 source(s) crawled  ==  due-gating ran and selected zero
                                       sources: successful no-work execution

3. Per-source failures are recorded in crawler_runs and counted in
   ``outcome.errors`` but do NOT prevent the done-line. The done-line
   attests CYCLE completion only; per-source success/failure remains
   operational-plane evidence (crawler_runs / collector health) and is
   never claimed here.
4. Exit code 2 = LockError = another legitimate execution holds the lock -
   explicitly "the system working as designed" (crawl_service.py). This is
   NOT an application failure; it is left UNKNOWN with an explanatory
   detail rather than mislabeled.
5. Any other non-zero exit or a missing done-line on exit 0 leaves
   execution_result None (UNKNOWN).
"""

from __future__ import annotations

import re
from typing import Any

EXTRACTOR_ID = "oem-radar/done-line"
EXTRACTOR_VERSION = 1

_DONE_RE = re.compile(
    r"^done:[ \t]*(\d+)[ \t]+source\(s\) crawled,[ \t]*"
    r"(\d+)[ \t]+snapshot\(s\),[ \t]*(\d+)[ \t]+event\(s\)",
    re.MULTILINE,
)


class OemRadarExecutionExtractor:
    id = EXTRACTOR_ID
    version = EXTRACTOR_VERSION
    clank_id = "oem-radar"

    def extract(self, output_text: str | None,
                *, exit_code: int | None = None) -> dict[str, Any]:
        provenance = {
            "extractor_id": self.id,
            "extractor_version": self.version,
            "evidence_source": "process-output",
        }
        if not output_text:
            return {"execution_result": None,
                    "execution_detail": "no output captured",
                    **provenance}

        match = _DONE_RE.search(output_text)
        if match:
            sources, snapshots, events = (int(g) for g in match.groups())
            errors = _errors_note(output_text)
            result = "no_work_due" if sources == 0 else "completed"
            detail = (f"cycle completed: {sources} source(s) crawled "
                      f"(due-gated), {snapshots} snapshot(s), {events} "
                      f"event(s); per-source outcomes remain operational-"
                      "plane evidence"
                      + (f"; {errors}" if errors else ""))
            return {"execution_result": result,
                    "execution_detail": detail,
                    **provenance}

        if "LockError" in output_text or (
                exit_code == 2 and "ERROR:" in output_text):
            # By-design contention: another legitimate execution holds the
            # lock. Not a failure; deliberately UNKNOWN, not failed.
            return {"execution_result": None,
                    "execution_detail": "lock contention (by-design blocked "
                                        "state; exit code 2)",
                    **provenance}

        return {"execution_result": None,
                "execution_detail": f"output did not match any attested "
                                    f"pattern (exit_code={exit_code})",
                **provenance}


def _errors_note(text: str) -> str | None:
    """Surface the participant's own error count when present in the same
    done-line block; per-source failure detail stays in crawler_runs."""
    match = re.search(r"(\d+)\s+error", text)
    return f"errors reported in cycle: {match.group(1)}" if match else None

#: Single shared instance; discovered lazily via execution_results.get_extractor.
EXTRACTOR = OemRadarExecutionExtractor()
