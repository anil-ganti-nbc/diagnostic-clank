"""Protocol existence tests (Stage 0)."""

from __future__ import annotations

from clank_runtime.config import ConfigurationProvider
from clank_runtime.events import EventExporter
from clank_runtime.health import HealthProvider
from clank_runtime.lifecycle import GracefulShutdownHook
from clank_runtime.metadata import MetadataProvider
from clank_runtime.operations import DiagnosticsProvider, OperationAdapter


def test_protocols_are_importable() -> None:
    assert ConfigurationProvider is not None
    assert HealthProvider is not None
    assert MetadataProvider is not None
    assert EventExporter is not None
    assert GracefulShutdownHook is not None
    assert OperationAdapter is not None
    assert DiagnosticsProvider is not None
