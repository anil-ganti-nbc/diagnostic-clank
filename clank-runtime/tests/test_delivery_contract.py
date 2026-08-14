"""Production Delivery Contract tests — dual health domains and release state."""

from __future__ import annotations

from datetime import UTC, datetime

from clank_runtime.contracts.delivery import (
    CollectionHealthReport,
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
from clank_runtime.contracts.enums import (
    ClankReleaseState,
    CollectionHealthState,
    DeliveryHealthState,
    DeploymentAcceptanceState,
    NotificationAuthorityRole,
    ProductionMode,
)
from clank_runtime.version import DELIVERY_CONTRACT_VERSION


def test_watch_clank_scenario_collection_healthy_delivery_missing() -> None:
    """17/17 sources healthy + no Discord must NOT be release HEALTHY."""
    dual = DualDomainHealth(
        clank_id="watch-clank",
        production_mode=ProductionMode.PRODUCTION,
        collection=CollectionHealthReport(
            state=CollectionHealthState.HEALTHY,
            sources_total=17,
            sources_healthy=17,
        ),
        delivery=DeliveryHealthReport(
            state=DeliveryHealthState.NOT_CONFIGURED,
            webhook_configured=False,
            reasons=["no Discord webhook configured"],
        ),
        acceptance=DeploymentAcceptanceState.PARTIAL,
        observed_at=datetime.now(UTC),
    )
    assert dual.collection.state == CollectionHealthState.HEALTHY
    assert dual.delivery.state == DeliveryHealthState.NOT_CONFIGURED
    assert dual.release_state == ClankReleaseState.DEGRADED
    assert dual.release_state != ClankReleaseState.HEALTHY


def test_healthy_requires_both_domains_and_verified_acceptance() -> None:
    dual = DualDomainHealth(
        clank_id="oem-radar",
        collection=CollectionHealthReport(state=CollectionHealthState.HEALTHY),
        delivery=DeliveryHealthReport(state=DeliveryHealthState.HEALTHY),
        acceptance=DeploymentAcceptanceState.VERIFIED,
    )
    assert dual.release_state == ClankReleaseState.HEALTHY


def test_baselining_mode_overrides() -> None:
    dual = DualDomainHealth(
        clank_id="feature-phone-clank",
        production_mode=ProductionMode.BASELINE,
        collection=CollectionHealthReport(state=CollectionHealthState.HEALTHY),
        delivery=DeliveryHealthReport(state=DeliveryHealthState.HEALTHY),
        acceptance=DeploymentAcceptanceState.VERIFIED,
    )
    assert dual.release_state == ClankReleaseState.BASELINING


def test_collection_failed_dominates() -> None:
    assert (
        compose_release_state(
            CollectionHealthState.FAILED,
            DeliveryHealthState.HEALTHY,
        )
        == ClankReleaseState.FAILED
    )


def test_notifications_without_webhook_fails_loudly() -> None:
    violations = check_production_config_invariants(
        notifications_enabled=True,
        webhook_configured=False,
    )
    assert any(v.code == "NOTIFICATIONS_WITHOUT_WEBHOOK" for v in violations)
    state = delivery_state_from_invariants(violations, notifications_enabled=True)
    assert state == DeliveryHealthState.FAILED


def test_threshold_above_max_score() -> None:
    violations = check_production_config_invariants(
        notifications_enabled=True,
        webhook_configured=True,
        notification_threshold=100.0,
        max_attainable_score=50.0,
    )
    assert any(v.code == "THRESHOLD_ABOVE_MAX_SCORE" for v in violations)


def test_authority_without_target() -> None:
    violations = check_production_config_invariants(
        notifications_enabled=True,
        webhook_configured=False,
        authority_role=NotificationAuthorityRole.AUTHORITATIVE_SENDER,
    )
    codes = {v.code for v in violations}
    assert "AUTHORITY_WITHOUT_TARGET" in codes


def test_canary_never_fabricates_production_event() -> None:
    result = DeliveryCanaryResult(
        clank_id="watch-clank",
        channel="discord",
        delivered=True,
        message="TEST/CANARY — ignore",
        attempted_at=datetime.now(UTC),
    )
    assert result.is_canary is True
    assert result.is_test is True
    assert result.fabricates_production_event is False
    assert result.enters_editorial_history is False


def test_deployment_acceptance_verified_only_when_complete() -> None:
    partial = DeploymentAcceptanceChecklist(
        clank_id="oem-radar",
        git_sha_verified=True,
        schema_at_head=True,
        db_integrity_ok=True,
    )
    assert partial.acceptance_state() == DeploymentAcceptanceState.PARTIAL

    full = DeploymentAcceptanceChecklist(
        clank_id="oem-radar",
        git_sha_verified=True,
        schema_at_head=True,
        db_integrity_ok=True,
        production_scheduler_exercised=True,
        baseline_protections_verified=True,
        delivery_runtime_sees_config=True,
        editorial_test_delivered=True,
        health_test_delivered=True,
        notification_authority_verified=True,
        no_duplicate_sender=True,
        no_stale_locks=True,
        repeat_run_stable=True,
    )
    assert full.acceptance_state() == DeploymentAcceptanceState.VERIFIED


def test_notification_authority_inspectable() -> None:
    auth = NotificationAuthority(
        clank_id="watch-clank",
        channel="discord",
        host_id="hetzner-1",
        role=NotificationAuthorityRole.AUTHORITATIVE_SENDER,
        notes="Windows is collection+GUI only",
    )
    assert auth.inspectable is True
    assert auth.role == NotificationAuthorityRole.AUTHORITATIVE_SENDER


def test_failure_corpus_blocks_promotion_when_regressing() -> None:
    specimen = FailureCorpusSpecimen(
        clank_id="watch-clank",
        benchmark_name="WatchBench",
        expected_behavior="emit product event and deliver Discord alert",
        actual_behavior="collectors green; no Discord path",
        root_cause="delivery path not configured; health collapsed to HEALTHY",
        remediation="dual-domain health + delivery contract",
        regression_status="fixed",
        would_catch_today=True,
    )
    assert specimen.blocks_promotion_if_regressing is True
    assert specimen.would_catch_today is True


def test_delivery_contract_version_present() -> None:
    dual = DualDomainHealth(clank_id="oem-radar")
    assert dual.schema_version == DELIVERY_CONTRACT_VERSION


def test_domains_remain_separately_queryable() -> None:
    dual = DualDomainHealth(
        clank_id="watch-clank",
        collection=CollectionHealthReport(
            state=CollectionHealthState.HEALTHY,
            sources_total=17,
            sources_healthy=17,
        ),
        delivery=DeliveryHealthReport(state=DeliveryHealthState.FAILED),
        acceptance=DeploymentAcceptanceState.VERIFIED,
    )
    # Explicit dual reporting — not collapsed
    assert dual.collection.state.value == "healthy"
    assert dual.delivery.state.value == "failed"
    assert dual.release_state == ClankReleaseState.DEGRADED
