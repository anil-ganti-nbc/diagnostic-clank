"""Event exporter protocol.

STAGE 0.5 BOUNDARY — interface only.
Forbidden here: JSONL writers, outbox spools, disk I/O, network publish.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from clank_runtime.contracts.events import EventEnvelope


@runtime_checkable
class EventExporter(Protocol):
    """Exports events according to the event contract.

    Concrete exporters (outbox, JSONL, etc.) are forbidden in Stage 0 / 0.5.
    """

    def export(self, event: EventEnvelope) -> None:
        """Export a single event envelope."""
        ...
