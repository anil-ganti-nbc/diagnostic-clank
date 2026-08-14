"""Enumerations for operational, release, source, delivery, and failure states.

Architecture v3. Semantic values are stable; additional members may be added
with a contract version bump. Do not remove members once published.
"""

from __future__ import annotations

from enum import StrEnum


class OperationalState(StrEnum):
    """High-level operational state of a clank process.

    Separate from :class:`ReleaseChannel` (maturity of the deployment).
    """

    STARTING = "starting"
    HEALTHY = "healthy"
    WARNING = "warning"
    IDLE = "idle"
    DEGRADED = "degraded"
    FAILED = "failed"
    PAUSED = "paused"
    STALE = "stale"
    OFFLINE = "offline"
    UNKNOWN = "unknown"
    EXPERIMENTAL = "experimental"


class ReleaseChannel(StrEnum):
    """Release channel classification for a clank deployment."""

    EXPERIMENTAL = "experimental"
    SOAKING = "soaking"
    STAGING = "staging"
    PRODUCTION = "production"
    REPAIR = "repair"
    DEPRECATED = "deprecated"


class IngestionState(StrEnum):
    """Ingestion pipeline state relative to expected freshness."""

    CURRENT = "current"
    DELAYED = "delayed"
    BACKLOGGED = "backlogged"
    STALLED = "stalled"
    REPLAYING = "replaying"
    QUARANTINED = "quarantined"
    UNKNOWN = "unknown"


class SourceLifecycleState(StrEnum):
    """Source promotion lifecycle (Great Audit SOURCE_PROMOTION_PROTOCOL).

    Promotion is always explicit. Fleet may display and gate transitions;
    it must never auto-promote.
    """

    DISCOVERED = "discovered"
    RESEARCH = "research"
    EXPERIMENTAL = "experimental"
    SOAK = "soak"
    PRODUCTION = "production"
    DISABLED = "disabled"
    QUARANTINED = "quarantined"


class SourceHealthStatus(StrEnum):
    """Per-source health as reported by a Clank to Fleet.

    Source-specific zero semantics remain Clank-owned. Fleet consumes the
    declared status; it does not reinterpret raw observed_count as healthy.
    Evidence: Watch Clank product-catalogue ZERO_ITEMS must not be HEALTHY.
    """

    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"
    BLOCKED_ZERO = "blocked_zero"
    ZERO_ITEMS = "zero_items"
    SKIPPED_OVERLAP = "skipped_overlap"
    BLOCKED = "blocked"
    WARNING = "warning"
    UNKNOWN = "unknown"
    NEVER_RUN = "never_run"


class DeliveryStatus(StrEnum):
    """Fleet-facing delivery accounting (Great Audit delivery contract).

    Clanks need not share one outbox implementation. Adapters map internal
    state onto these values. LIMITED capability is reported when unmapped.
    """

    EVENT_CREATED = "event_created"
    DELIVERY_PENDING = "delivery_pending"
    DELIVERY_SUCCEEDED = "delivery_succeeded"
    DELIVERY_FAILED_RETRYABLE = "delivery_failed_retryable"
    DELIVERY_FAILED_FINAL = "delivery_failed_final"
    DELIVERY_SUPPRESSED_BASELINE = "delivery_suppressed_baseline"
    DELIVERY_SUPPRESSED_POLICY = "delivery_suppressed_policy"
    DELIVERY_UNKNOWN = "delivery_unknown"


class RunKind(StrEnum):
    """Semantic kind of a collector run (baseline vs normal etc.)."""

    BASELINE_BUILD = "baseline_build"
    NORMAL_RUN = "normal_run"
    RECOVERY_RUN = "recovery_run"
    REPLAY_RUN = "replay_run"
    SOAK_RUN = "soak_run"
    MANUAL_PROBE = "manual_probe"
    FALLBACK_RUN = "fallback_run"


class FailureClass(StrEnum):
    """Shared failure taxonomy (Great Audit FAILURE_TAXONOMY).

    Prefer UNKNOWN over a false diagnosis. Machine-readable; human messages
    remain free-text alongside.
    """

    SOURCE_GAP = "source_gap"
    REGION_GAP = "region_gap"
    DISCOVERY_FAILURE = "discovery_failure"
    FETCH_FAILURE = "fetch_failure"
    PARSER_FAILURE = "parser_failure"
    IDENTITY_FAILURE = "identity_failure"
    FILTER_FALSE_NEGATIVE = "filter_false_negative"
    FILTER_FALSE_POSITIVE = "filter_false_positive"
    STATE_FAILURE = "state_failure"
    FALSE_DELETION = "false_deletion"
    EVENT_FAILURE = "event_failure"
    DEDUPE_FAILURE = "dedupe_failure"
    CLASSIFICATION_FAILURE = "classification_failure"
    DELIVERY_FAILURE = "delivery_failure"
    LATENCY_FAILURE = "latency_failure"
    DURABILITY_FAILURE = "durability_failure"
    OBSERVABILITY_FAILURE = "observability_failure"
    CONFIGURATION_DRIFT = "configuration_drift"
    BASELINE_POLLUTION = "baseline_pollution"
    CATALOGUE_COLLAPSE = "catalogue_collapse"
    CHALLENGE_PAGE_AS_ZERO = "challenge_page_as_zero"
    OVERLAP_RUN = "overlap_run"
    UNKNOWN = "unknown"


class ActionSafetyClass(StrEnum):
    """Classification of control actions for offline queue / reconnect safety.

    SAFE_OFFLINE may auto-sync when HQ returns if idempotent.
    STALE_SENSITIVE must never auto-execute hours later; require reconfirmation.
    HIGH_RISK always requires live confirmation.
    """

    SAFE_OFFLINE = "safe_offline"
    STALE_SENSITIVE = "stale_sensitive"
    HIGH_RISK = "high_risk"
    READ_ONLY = "read_only"


class FallbackLevel(StrEnum):
    """Desktop/local fallback capability levels for a Clank.

    Level 3 requires fencing. Do not advertise Level 3 without ownership support.
    """

    LEVEL_0 = "level_0"  # observability only
    LEVEL_1 = "level_1"  # offline ledger/cache
    LEVEL_2 = "level_2"  # read-only diagnostics + local probes
    LEVEL_3 = "level_3"  # full local fallback execution with fencing


class LedgerOutcome(StrEnum):
    """Human Ledger HIT/MISS outcome."""

    HIT = "hit"
    MISS = "miss"
    PENDING = "pending"
    WROTE = "wrote"
    DIDNT_WRITE = "didnt_write"
    UNKNOWN = "unknown"


class OwnershipRole(StrEnum):
    """Who currently owns production execution for a Clank."""

    NAS_PRIMARY = "nas_primary"
    DESKTOP_FALLBACK = "desktop_fallback"
    UNCLAIMED = "unclaimed"
    CONTESTED = "contested"
    UNKNOWN = "unknown"


# --- Production Delivery Contract (fleet-wide invariant) ---------------------


class CollectionHealthState(StrEnum):
    """Health of collection / persistence only.

    Must never be collapsed with delivery health into a single misleading HEALTHY.
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNKNOWN = "unknown"
    NEVER_RUN = "never_run"


class DeliveryHealthState(StrEnum):
    """Health of the external notification / delivery path.

    Independent of collection. Missing webhook with notifications enabled is
    DEGRADED or FAILED, never overall HEALTHY.
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    NOT_CONFIGURED = "not_configured"
    LIMITED = "limited"
    UNKNOWN = "unknown"


class ClankReleaseState(StrEnum):
    """Mandatory fleet-wide release-state vocabulary.

    HEALTHY = collection AND delivery contract verified.
    DEGRADED = core collection works, but a required output path is unavailable.
    PARTIAL = deployment exists but has not passed full production acceptance.
    FAILED = core collection/persistence path broken.
    BASELINING = intentionally suppressing external intelligence while initial state is established.
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    PARTIAL = "partial"
    FAILED = "failed"
    BASELINING = "baselining"
    UNKNOWN = "unknown"


class ProductionMode(StrEnum):
    """Baseline / validation / production mode distinction.

    Production semantics must never silently inherit baseline defaults
    (emit_events=False, notify=False).
    """

    BASELINE = "baseline"
    VALIDATION = "validation"
    PRODUCTION = "production"


class DeploymentAcceptanceState(StrEnum):
    """Deployment is not complete when image builds and timers are green."""

    VERIFIED = "verified"
    PARTIAL = "partial"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNKNOWN = "unknown"


class NotificationAuthorityRole(StrEnum):
    """Exactly one host is authoritative for each external notification channel."""

    AUTHORITATIVE_SENDER = "authoritative_sender"
    COLLECTION_ONLY = "collection_only"
    GUI_ONLY = "gui_only"
    DISABLED = "disabled"
    UNKNOWN = "unknown"
