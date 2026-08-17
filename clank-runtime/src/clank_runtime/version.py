"""Package version and contract version constants for clank-runtime.

Architecture v3 introduces independent contract versions for each surface.
Bump the relevant constant when a contract's serialised shape or semantics
change in a breaking way. Additive optional fields may keep the same version
if documented as backward-compatible.
"""

from __future__ import annotations

__version__ = "0.1.0.dev0"

# Contract versions are independent of package version.
RUNTIME_CONTRACT_VERSION = "0.2.0-v3"
EVENT_CONTRACT_VERSION = "0.2.0-v3"
HEALTH_CONTRACT_VERSION = "0.3.0-v3"
OPERATION_CONTRACT_VERSION = "0.2.0-v3"
TELEMETRY_CONTRACT_VERSION = "0.1.0-v3"
ADAPTER_CONTRACT_VERSION = "0.1.0-v3"
LEDGER_CONTRACT_VERSION = "0.1.0-v3"
MACHINE_CONTRACT_VERSION = "0.1.0-v3"
FALLBACK_CONTRACT_VERSION = "0.1.0-v3"
CACHE_SCHEMA_VERSION = "0.1.0-v3"
DELIVERY_CONTRACT_VERSION = "0.1.0-v3"
KNOWLEDGE_CONTRACT_VERSION = "0.1.0-archivist"
DIAGNOSTIC_CONTRACT_VERSION = "0.1.0"
