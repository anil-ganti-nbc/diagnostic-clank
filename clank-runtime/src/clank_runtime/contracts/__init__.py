"""Public contract models for Architecture v3.

Import from submodules for clarity; this package re-exports the primary types.
"""

from __future__ import annotations


from clank_runtime.contracts.delivery import (
    CollectionHealthReport,
    ConfigInvariantViolation,
    DeliveryCanaryResult,
    DeliveryHealthReport,
    DeploymentAcceptanceChecklist,
    DualDomainHealth,
    FailureCorpusSpecimen,
    NotificationAuthority,
    check_production_config_invariants,
    compose_release_state,
    delivery_state_from_invariants,
)
from clank_runtime.contracts.actions import (
    OfflineQueueItem,
    classify_operation,
    may_auto_sync,
    must_reconfirm,
)
from clank_runtime.contracts.adapter import (
    AdapterCapabilities,
    AdapterDescriptor,
    AdapterStatus,
    UnsupportedOperationError,
)
from clank_runtime.contracts.enums import (
    ActionSafetyClass,
    ProductionMode,
    NotificationAuthorityRole,
    DeploymentAcceptanceState,
    DeliveryHealthState,
    CollectionHealthState,
    ClankReleaseState,
    DeliveryStatus,
    FailureClass,
    FallbackLevel,
    IngestionState,
    LedgerOutcome,
    OperationalState,
    OwnershipRole,
    ReleaseChannel,
    RunKind,
    SourceHealthStatus,
    SourceLifecycleState,
)
from clank_runtime.contracts.events import EventEnvelope
from clank_runtime.contracts.failure import FailureReport
from clank_runtime.contracts.fallback import (
    FallbackDeclaration,
    OwnershipState,
    OwnershipToken,
    can_start_fallback,
    requires_fencing_for_level,
)
from clank_runtime.contracts.health import HealthPayload, SourceHealthEntry
from clank_runtime.contracts.identity import RuntimeIdentity
from clank_runtime.contracts.ledger import LedgerEntry, ledger_join_keys
from clank_runtime.contracts.lifecycle import (
    ALLOWED_SOURCE_TRANSITIONS,
    SoakStatus,
    SourceLifecycleRecord,
    can_transition,
)
from clank_runtime.contracts.machine import (
    MachineCapabilities,
    MachineCapabilityReport,
    SupportedClankEntry,
)
from clank_runtime.contracts.operations import (
    OperationResult,
    OperationState,
    OperationType,
)
from clank_runtime.contracts.telemetry import TelemetryEnvelope, TelemetryEventRecord

__all__ = [
    "delivery_state_from_invariants",
    "compose_release_state",
    "check_production_config_invariants",
    "ProductionMode",
    "NotificationAuthorityRole",
    "NotificationAuthority",
    "FailureCorpusSpecimen",
    "DualDomainHealth",
    "DeploymentAcceptanceState",
    "DeploymentAcceptanceChecklist",
    "DeliveryHealthState",
    "DeliveryHealthReport",
    "DeliveryCanaryResult",
    "ConfigInvariantViolation",
    "CollectionHealthReport",
    "CollectionHealthState",
    "ClankReleaseState",
    "ALLOWED_SOURCE_TRANSITIONS",
    "ActionSafetyClass",
    "AdapterCapabilities",
    "AdapterDescriptor",
    "AdapterStatus",
    "DeliveryStatus",
    "EventEnvelope",
    "FailureClass",
    "FailureReport",
    "FallbackDeclaration",
    "FallbackLevel",
    "HealthPayload",
    "IngestionState",
    "LedgerEntry",
    "LedgerOutcome",
    "MachineCapabilities",
    "MachineCapabilityReport",
    "OfflineQueueItem",
    "OperationalState",
    "OperationResult",
    "OperationState",
    "OperationType",
    "OwnershipRole",
    "OwnershipState",
    "OwnershipToken",
    "ReleaseChannel",
    "RunKind",
    "RuntimeIdentity",
    "SoakStatus",
    "SourceHealthEntry",
    "SourceHealthStatus",
    "SourceLifecycleRecord",
    "SourceLifecycleState",
    "SupportedClankEntry",
    "TelemetryEnvelope",
    "TelemetryEventRecord",
    "UnsupportedOperationError",
    "can_start_fallback",
    "can_transition",
    "classify_operation",
    "ledger_join_keys",
    "may_auto_sync",
    "must_reconfirm",
    "requires_fencing_for_level",
]
