"""Scheduler-fire attestation probe contract (P-4.4.1).

Owned by Diagnostic Clank's adapter/probe plane. Motherclank consumes
canonical traces; never touches schedulers or host state.

The probe reads EXISTING host evidence (cron logs, journal entries,
systemd timer last-trigger timestamps) and converts it into canonical
scheduler_trace records using ``motherclank.scheduler_traces.make_trace``.

This module defines the INTERFACE the probe must implement so any
scheduler type can be supported without Motherclank learning about
cron vs systemd vs anything else.

Implementation classes live per-scheduler-type; the registry dispatches
by declared scheduler_type from the lane config.
"""

from __future__ import annotations

from typing import Any, Protocol


class SchedulerFireProbe(Protocol):
    """Read-only host-side probe that positively observes scheduler fires."""

    scheduler_type: str

    def probe(self, *, clank_id: str, unit_or_job: str,
              since: str | None = None) -> list[dict[str, Any]]:
        """Return canonical trace dicts for observed fires.

        Each dict must be valid input to
        ``motherclank.scheduler_traces.make_trace``.

        Returns empty list when no fire evidence is found (this is honest
        UNKNOWN, never fabricated as a non-fire).
        """
        ...
