"""clank-runtime: Shared runtime contracts for Unified Clank Infrastructure.

Stage 0 skeleton only. No production behavior is implemented.
"""

from __future__ import annotations

from clank_runtime.version import (
    EVENT_CONTRACT_VERSION,
    HEALTH_CONTRACT_VERSION,
    OPERATION_CONTRACT_VERSION,
    RUNTIME_CONTRACT_VERSION,
    __version__,
)

__all__ = [
    "__version__",
    "RUNTIME_CONTRACT_VERSION",
    "EVENT_CONTRACT_VERSION",
    "HEALTH_CONTRACT_VERSION",
    "OPERATION_CONTRACT_VERSION",
]
