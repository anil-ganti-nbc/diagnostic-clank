"""clank-runtime: Shared contracts for Unified Clank Infrastructure.

Architecture v3 — control-plane contracts only. No production scraping,
no production databases, no secret material.
"""

from __future__ import annotations

from clank_runtime.version import (
    ADAPTER_CONTRACT_VERSION,
    CACHE_SCHEMA_VERSION,
    EVENT_CONTRACT_VERSION,
    FALLBACK_CONTRACT_VERSION,
    HEALTH_CONTRACT_VERSION,
    LEDGER_CONTRACT_VERSION,
    MACHINE_CONTRACT_VERSION,
    OPERATION_CONTRACT_VERSION,
    RUNTIME_CONTRACT_VERSION,
    TELEMETRY_CONTRACT_VERSION,
    __version__,
)

__all__ = [
    "__version__",
    "ADAPTER_CONTRACT_VERSION",
    "CACHE_SCHEMA_VERSION",
    "EVENT_CONTRACT_VERSION",
    "FALLBACK_CONTRACT_VERSION",
    "HEALTH_CONTRACT_VERSION",
    "LEDGER_CONTRACT_VERSION",
    "MACHINE_CONTRACT_VERSION",
    "OPERATION_CONTRACT_VERSION",
    "RUNTIME_CONTRACT_VERSION",
    "TELEMETRY_CONTRACT_VERSION",
]
