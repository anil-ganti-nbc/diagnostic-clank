"""Production Delivery Contract — fleet-wide invariant.

A Clank is not operational merely because collectors run successfully.
Collection health and delivery health are distinct domains.
Green scrapers are necessary; green delivery is mandatory.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from clank_runtime.contracts.enums import (
    ClankReleaseState,
    CollectionHealthState,
    DeliveryHealthState,
    DeploymentAcceptanceState,
    NotificationAuthorityRole,
    ProductionMode,
)
from clank_runtime.version import DELIVERY_CONTRACT_VERSION


# ---------------------------------------------------------------------------
# Dual-domain health
# ---------------------------------------------------------------------------


class CollectionHealthReport(BaseModel):
    """Collection / persistence domain only."""

    model_config = ConfigDict(extra="forbid")

    state: CollectionHealthState = CollectionHealthState.UNKNOWN
    sources_total: int | None = Field(default=None, ge=0)
    sources_healthy: int | None = Field(default=None, ge=0)
    sources_warning: int | None = Field(default=None, ge=0)
    sources_failed: int | None = Field(default=None, ge=0)
    last_success_at: datetime | None = None
    last_attempt_at: datetime | None = None
    reasons: list[str] = Field(default_factory=list)


class DeliveryHealthReport(BaseModel):
    """Notification / external delivery domain only."""

    model_config = ConfigDict(extra="forbid")

    state: DeliveryHealthState = DeliveryHealthState.UNKNOWN
    editorial_path_healthy: bool | None = None
    health_alert_path_healthy: bool | None = None
    authority_configured: bool | None = None
    secrets_visible: bool | None = None
    webhook_configured: bool | None = None
    last_successful_delivery_at: datetime | None = None
    last_canary_at: datetime | None = None
    last_canary_ok: bool | None = None
    pending_count: int | None = Field(default=None, ge=0)
    failed_count: int | None = Field(default=None, ge=0)
    reasons: list[str] = Field(default_factory=list)


def compose_release_state(
    collection: CollectionHealthState,
    delivery: DeliveryHealthState,
    *,
    mode: ProductionMode = ProductionMode.PRODUCTION,
    acceptance: DeploymentAcceptanceState = DeploymentAcceptanceState.UNKNOWN,
) -> ClankReleaseState:
    """Derive fleet release state. Never report HEALTHY if delivery is broken.

    This is the rule that would have prevented Watch Clank looking
    '17/17 HEALTHY' while Discord was nonexistent.
    """
    if mode == ProductionMode.BASELINE:
        return ClankReleaseState.BASELINING

    if collection == CollectionHealthState.FAILED:
        return ClankReleaseState.FAILED

    # Delivery unavailable while collection is green is DEGRADED — never HEALTHY.
    # This is the Watch Clank rule: 17/17 collectors + missing Discord ≠ HEALTHY.
    if collection == CollectionHealthState.HEALTHY and delivery in (
        DeliveryHealthState.DEGRADED,
        DeliveryHealthState.FAILED,
        DeliveryHealthState.NOT_CONFIGURED,
        DeliveryHealthState.LIMITED,
        DeliveryHealthState.UNKNOWN,
    ):
        return ClankReleaseState.DEGRADED

    if collection == CollectionHealthState.HEALTHY and delivery == DeliveryHealthState.HEALTHY:
        if acceptance == DeploymentAcceptanceState.VERIFIED:
            return ClankReleaseState.HEALTHY
        # Collection+delivery green but acceptance incomplete → PARTIAL
        return ClankReleaseState.PARTIAL

    if collection == CollectionHealthState.DEGRADED:
        return ClankReleaseState.DEGRADED

    return ClankReleaseState.UNKNOWN


class DualDomainHealth(BaseModel):
    """Combined health that never collapses domains into one misleading flag."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default=DELIVERY_CONTRACT_VERSION, min_length=1)
    clank_id: str = Field(..., min_length=1, pattern=r"^[a-z][a-z0-9-]*$")
    production_mode: ProductionMode = ProductionMode.PRODUCTION
    collection: CollectionHealthReport = Field(default_factory=CollectionHealthReport)
    delivery: DeliveryHealthReport = Field(default_factory=DeliveryHealthReport)
    release_state: ClankReleaseState = ClankReleaseState.UNKNOWN
    acceptance: DeploymentAcceptanceState = DeploymentAcceptanceState.UNKNOWN
    observed_at: datetime | None = None
    is_stale_cache: bool = False
    extensions: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _derive_release_state(self) -> DualDomainHealth:
        self.release_state = compose_release_state(
            self.collection.state,
            self.delivery.state,
            mode=self.production_mode,
            acceptance=self.acceptance,
        )
        return self


# ---------------------------------------------------------------------------
# Configuration invariants
# ---------------------------------------------------------------------------


class ConfigInvariantViolation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    severity: str = "error"  # error | warning


def check_production_config_invariants(
    *,
    notifications_enabled: bool,
    webhook_configured: bool,
    notification_threshold: float | None = None,
    max_attainable_score: float | None = None,
    authority_role: NotificationAuthorityRole = NotificationAuthorityRole.UNKNOWN,
    source_enabled: bool = True,
    scheduler_defined: bool = True,
    collector_executable: bool = True,
    schema_at_head: bool = True,
) -> list[ConfigInvariantViolation]:
    """Impossible production configuration must fail loudly or degrade health."""
    violations: list[ConfigInvariantViolation] = []

    if notifications_enabled and not webhook_configured:
        violations.append(
            ConfigInvariantViolation(
                code="NOTIFICATIONS_WITHOUT_WEBHOOK",
                message="notifications enabled but webhook missing",
            )
        )

    if (
        authority_role == NotificationAuthorityRole.AUTHORITATIVE_SENDER
        and not webhook_configured
    ):
        violations.append(
            ConfigInvariantViolation(
                code="AUTHORITY_WITHOUT_TARGET",
                message="authoritative sender configured without delivery target",
            )
        )

    if (
        notification_threshold is not None
        and max_attainable_score is not None
        and notification_threshold > max_attainable_score
    ):
        violations.append(
            ConfigInvariantViolation(
                code="THRESHOLD_ABOVE_MAX_SCORE",
                message=(
                    f"notification threshold {notification_threshold} > "
                    f"maximum attainable score {max_attainable_score}"
                ),
            )
        )

    if source_enabled and not scheduler_defined:
        violations.append(
            ConfigInvariantViolation(
                code="SOURCE_WITHOUT_SCHEDULER",
                message="source enabled without scheduler definition",
            )
        )

    if scheduler_defined and not collector_executable:
        violations.append(
            ConfigInvariantViolation(
                code="SCHEDULER_WITHOUT_COLLECTOR",
                message="scheduler enabled without executable collector",
            )
        )

    if not schema_at_head:
        violations.append(
            ConfigInvariantViolation(
                code="SCHEMA_BELOW_HEAD",
                message="schema below required version",
            )
        )

    return violations


def delivery_state_from_invariants(
    violations: list[ConfigInvariantViolation],
    *,
    notifications_enabled: bool,
) -> DeliveryHealthState:
    if not notifications_enabled:
        return DeliveryHealthState.NOT_CONFIGURED
    errors = [v for v in violations if v.severity == "error"]
    if any(v.code in {"NOTIFICATIONS_WITHOUT_WEBHOOK", "AUTHORITY_WITHOUT_TARGET"} for v in errors):
        return DeliveryHealthState.FAILED
    if errors:
        return DeliveryHealthState.DEGRADED
    return DeliveryHealthState.HEALTHY


# ---------------------------------------------------------------------------
# Delivery canary
# ---------------------------------------------------------------------------


class DeliveryCanaryResult(BaseModel):
    """Safe delivery canary — exercises real transport without fabricating events."""

    model_config = ConfigDict(extra="forbid")

    canary_id: str = Field(default_factory=lambda: str(uuid4()))
    clank_id: str
    channel: str  # discord | email | health | …
    is_test: bool = True
    is_canary: bool = True
    fabricates_production_event: bool = False
    enters_editorial_history: bool = False
    delivered: bool = False
    transport_status: str | None = None
    attempted_at: datetime | None = None
    message: str | None = Field(
        default=None,
        description="Must identify itself clearly as TEST/CANARY to operators.",
    )


# ---------------------------------------------------------------------------
# Notification authority
# ---------------------------------------------------------------------------


class NotificationAuthority(BaseModel):
    """Exactly one host is authoritative per external notification channel."""

    model_config = ConfigDict(extra="forbid")

    clank_id: str
    channel: str
    host_id: str
    role: NotificationAuthorityRole
    inspectable: bool = True
    notes: str | None = None


# ---------------------------------------------------------------------------
# Deployment acceptance
# ---------------------------------------------------------------------------


class DeploymentAcceptanceChecklist(BaseModel):
    """VERIFIED only when the full production path is proven."""

    model_config = ConfigDict(extra="forbid")

    clank_id: str
    git_sha_verified: bool = False
    schema_at_head: bool = False
    db_integrity_ok: bool = False
    production_scheduler_exercised: bool = False
    baseline_protections_verified: bool = False
    delivery_runtime_sees_config: bool = False
    editorial_test_delivered: bool = False
    health_test_delivered: bool = False
    notification_authority_verified: bool = False
    no_duplicate_sender: bool = False
    no_stale_locks: bool = False
    repeat_run_stable: bool = False

    def acceptance_state(self) -> DeploymentAcceptanceState:
        flags = [
            self.git_sha_verified,
            self.schema_at_head,
            self.db_integrity_ok,
            self.production_scheduler_exercised,
            self.baseline_protections_verified,
            self.delivery_runtime_sees_config,
            self.editorial_test_delivered,
            self.health_test_delivered,
            self.notification_authority_verified,
            self.no_duplicate_sender,
            self.no_stale_locks,
            self.repeat_run_stable,
        ]
        if all(flags):
            return DeploymentAcceptanceState.VERIFIED
        if not self.db_integrity_ok or not self.schema_at_head:
            return DeploymentAcceptanceState.FAILED
        if any(flags):
            return DeploymentAcceptanceState.PARTIAL
        return DeploymentAcceptanceState.UNKNOWN


# ---------------------------------------------------------------------------
# Failure corpus / ClankBench specimen
# ---------------------------------------------------------------------------


class FailureCorpusSpecimen(BaseModel):
    """One real-world miss preserved for regression: WOULD CURRENT CLANK CATCH THIS TODAY?"""

    model_config = ConfigDict(extra="forbid")

    specimen_id: str = Field(default_factory=lambda: str(uuid4()))
    clank_id: str
    benchmark_name: str | None = Field(
        default=None,
        description="WatchBench, OEMBench, PhoneBench, …",
    )
    signal_source: str | None = None
    earliest_public_at: datetime | None = None
    clank_observed_at: datetime | None = None
    expected_behavior: str
    actual_behavior: str
    root_cause: str | None = None
    remediation: str | None = None
    regression_status: str = Field(
        default="open",
        description="open | fixed | regressing | waived",
    )
    would_catch_today: bool | None = None
    blocks_promotion_if_regressing: bool = True
