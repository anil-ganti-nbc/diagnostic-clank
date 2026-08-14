"""Architecture v3 contract tests — telemetry, failure, lifecycle, adapter,
machine, fallback fencing, offline queue, ledger, health semantics.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError

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
    DeliveryStatus,
    FailureClass,
    FallbackLevel,
    LedgerOutcome,
    OperationalState,
    OwnershipRole,
    ReleaseChannel,
    RunKind,
    SourceHealthStatus,
    SourceLifecycleState,
)
from clank_runtime.contracts.fallback import (
    FallbackDeclaration,
    OwnershipState,
    OwnershipToken,
    can_start_fallback,
    requires_fencing_for_level,
)
from clank_runtime.contracts.health import HealthPayload, SourceHealthEntry
from clank_runtime.contracts.ledger import LedgerEntry, ledger_join_keys
from clank_runtime.contracts.lifecycle import can_transition
from clank_runtime.contracts.machine import (
    MachineCapabilities,
    MachineCapabilityReport,
    SupportedClankEntry,
)
from clank_runtime.contracts.operations import OperationType
from clank_runtime.contracts.telemetry import TelemetryEnvelope, TelemetryEventRecord
from clank_runtime.version import (
    HEALTH_CONTRACT_VERSION,
    TELEMETRY_CONTRACT_VERSION,
    __version__,
)


def test_package_version_v3() -> None:
    assert __version__ == "0.1.0.dev0"


# --- Telemetry ----------------------------------------------------------------

def test_telemetry_envelope_roundtrip() -> None:
    env = TelemetryEnvelope(
        clank_id="oem-radar",
        run_id="run-1",
        source_id="gmktec-shopify",
        source_status=SourceHealthStatus.OK,
        observed_count=42,
        accepted_count=40,
        rejected_count=2,
        run_kind=RunKind.NORMAL_RUN,
        events=[
            TelemetryEventRecord(
                lead_id="lead-abc",
                source_url="https://example.com/p/1",
                classification="new_product",
                delivery_status=DeliveryStatus.DELIVERY_SUCCEEDED,
                is_baseline=False,
            )
        ],
    )
    data = env.model_dump(mode="json")
    restored = TelemetryEnvelope.model_validate(data)
    assert restored.schema_version == TELEMETRY_CONTRACT_VERSION
    assert restored.events[0].lead_id == "lead-abc"
    assert restored.source_status == SourceHealthStatus.OK


def test_telemetry_rejects_bad_clank_id() -> None:
    with pytest.raises(ValidationError):
        TelemetryEnvelope(clank_id="OEM_Radar", run_id="r1")


def test_telemetry_baseline_event_flag() -> None:
    ev = TelemetryEventRecord(lead_id="b1", is_baseline=True, delivery_status=DeliveryStatus.DELIVERY_SUPPRESSED_BASELINE)
    assert ev.is_baseline is True


# --- Failure taxonomy ---------------------------------------------------------

def test_failure_class_unknown_default() -> None:
    assert FailureClass.UNKNOWN == "unknown"
    assert FailureClass.FALSE_DELETION == "false_deletion"
    assert FailureClass.CATALOGUE_COLLAPSE == "catalogue_collapse"


# --- Source lifecycle ---------------------------------------------------------

def test_lifecycle_allowed_transitions() -> None:
    assert can_transition(SourceLifecycleState.EXPERIMENTAL, SourceLifecycleState.SOAK)
    assert can_transition(SourceLifecycleState.SOAK, SourceLifecycleState.PRODUCTION)
    assert not can_transition(SourceLifecycleState.DISCOVERED, SourceLifecycleState.PRODUCTION)
    assert not can_transition(SourceLifecycleState.PRODUCTION, SourceLifecycleState.DISCOVERED)


# --- Adapter capabilities -----------------------------------------------------

def test_adapter_unsupported_operation() -> None:
    caps = AdapterCapabilities(supports_manual_run=False)
    assert caps.supports_manual_run is False
    err = UnsupportedOperationError("watch-clank", "manual_run")
    assert "watch-clank" in str(err)
    assert "manual_run" in str(err)


def test_adapter_descriptor_roundtrip() -> None:
    d = AdapterDescriptor(
        clank_id="feature-phone-clank",
        clank_version="0.0.1",
        release_channel=ReleaseChannel.SOAKING,
        capabilities=AdapterCapabilities(supports_health=True, supports_telemetry=True),
    )
    restored = AdapterDescriptor.model_validate(d.model_dump())
    assert restored.capabilities.supports_health is True
    assert restored.capabilities.supports_local_fallback is False


def test_adapter_status_stale_flag() -> None:
    s = AdapterStatus(clank_id="oem-radar", operational_state=OperationalState.HEALTHY, is_stale=True)
    assert s.is_stale is True


# --- Machine capability -------------------------------------------------------

def test_machine_can_fallback() -> None:
    report = MachineCapabilityReport(
        machine_id="laptop-1",
        platform="linux",
        capabilities=MachineCapabilities(python_available=True, network_reachable=True),
        supported_clanks=[
            SupportedClankEntry(
                clank_id="feature-phone-clank",
                max_fallback_level=FallbackLevel.LEVEL_2,
                local_runtime_ready=True,
                fencing_supported=False,
            )
        ],
    )
    assert report.can_fallback("feature-phone-clank", FallbackLevel.LEVEL_1)
    assert not report.can_fallback("feature-phone-clank", FallbackLevel.LEVEL_3)
    assert not report.can_fallback("oem-radar", FallbackLevel.LEVEL_0)


# --- Fallback fencing ---------------------------------------------------------

def test_level3_requires_fencing() -> None:
    assert requires_fencing_for_level(FallbackLevel.LEVEL_3)
    assert not requires_fencing_for_level(FallbackLevel.LEVEL_1)


def test_fallback_refused_when_nas_uncertain() -> None:
    decl = FallbackDeclaration(clank_id="oem-radar", max_level=FallbackLevel.LEVEL_3)
    ownership = OwnershipState(clank_id="oem-radar", role=OwnershipRole.UNCLAIMED, epoch=1)
    now = datetime.now(UTC)
    ok, reason = can_start_fallback(
        declaration=decl,
        machine_supports=True,
        ownership=ownership,
        requested_level=FallbackLevel.LEVEL_3,
        now=now,
        nas_definitely_offline=False,
    )
    assert not ok
    assert "uncertain" in reason.lower() or "split-brain" in reason.lower()


def test_fallback_level3_needs_valid_token() -> None:
    decl = FallbackDeclaration(clank_id="oem-radar", max_level=FallbackLevel.LEVEL_3)
    now = datetime.now(UTC)
    token = OwnershipToken(
        clank_id="oem-radar",
        role=OwnershipRole.DESKTOP_FALLBACK,
        epoch=2,
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        issuer="desktop:laptop-1",
        machine_id="laptop-1",
    )
    ownership = OwnershipState(
        clank_id="oem-radar",
        role=OwnershipRole.DESKTOP_FALLBACK,
        epoch=2,
        token=token,
    )
    ok, reason = can_start_fallback(
        declaration=decl,
        machine_supports=True,
        ownership=ownership,
        requested_level=FallbackLevel.LEVEL_3,
        now=now,
        nas_definitely_offline=True,
    )
    assert ok, reason


def test_fallback_level3_refused_without_token() -> None:
    decl = FallbackDeclaration(clank_id="oem-radar", max_level=FallbackLevel.LEVEL_3)
    ownership = OwnershipState(clank_id="oem-radar", role=OwnershipRole.UNCLAIMED, epoch=0)
    now = datetime.now(UTC)
    ok, reason = can_start_fallback(
        declaration=decl,
        machine_supports=True,
        ownership=ownership,
        requested_level=FallbackLevel.LEVEL_3,
        now=now,
        nas_definitely_offline=True,
    )
    assert not ok
    assert "token" in reason.lower()


def test_expired_token_invalid() -> None:
    now = datetime.now(UTC)
    token = OwnershipToken(
        clank_id="oem-radar",
        role=OwnershipRole.DESKTOP_FALLBACK,
        epoch=1,
        issued_at=now - timedelta(hours=2),
        expires_at=now - timedelta(hours=1),
        issuer="desktop:x",
    )
    assert token.is_expired(now)
    assert not token.is_valid_for("oem-radar", OwnershipRole.DESKTOP_FALLBACK, now)


# --- Offline queue / action safety --------------------------------------------

def test_stale_sensitive_ops_must_reconfirm() -> None:
    assert classify_operation(OperationType.RESTART) == ActionSafetyClass.STALE_SENSITIVE
    assert classify_operation(OperationType.DEPLOY) == ActionSafetyClass.HIGH_RISK
    assert classify_operation(OperationType.STATUS) == ActionSafetyClass.READ_ONLY


def test_safe_offline_may_auto_sync() -> None:
    item = OfflineQueueItem(
        created_at=datetime.now(UTC),
        safety_class=ActionSafetyClass.SAFE_OFFLINE,
        action_type="ledger_entry",
        auto_sync_eligible=True,
    )
    assert may_auto_sync(item)
    assert not must_reconfirm(item)


def test_stale_restart_must_not_auto_sync() -> None:
    item = OfflineQueueItem(
        created_at=datetime.now(UTC),
        safety_class=ActionSafetyClass.STALE_SENSITIVE,
        action_type="operation",
        payload={"op": "restart"},
        auto_sync_eligible=True,  # even if flagged, must not auto-run
    )
    assert not may_auto_sync(item)
    assert must_reconfirm(item)


# --- Ledger -------------------------------------------------------------------

def test_ledger_entry_join_keys() -> None:
    entry = LedgerEntry(
        recorded_at=datetime.now(UTC),
        entry_date=date(2026, 8, 14),
        clank_id="watch-clank",
        lead_id="lead-99",
        source_url="https://example.com/w/1",
        outcome=LedgerOutcome.HIT,
    )
    keys = ledger_join_keys(entry)
    assert keys["lead_id"] == "lead-99"
    assert keys["clank_id"] == "watch-clank"
    assert keys["entry_date"] == "2026-08-14"


# --- Health: source-semantic zero ---------------------------------------------

def test_health_payload_distinguishes_source_status() -> None:
    """Product catalogue ZERO_ITEMS is a source status, not overall HEALTHY by fiat."""
    payload = HealthPayload(
        clank_id="watch-clank",
        overall_status=OperationalState.WARNING,
        sources=[
            SourceHealthEntry(
                source_id="seiko_products",
                status=SourceHealthStatus.ZERO_ITEMS,
                observed_count=0,
                previous_observed_count=50,
                health_reason="empty_catalogue_after_prior_success",
            ),
            SourceHealthEntry(
                source_id="monochrome_rss",
                status=SourceHealthStatus.ZERO_ITEMS,
                observed_count=0,
                health_reason="empty_news_cycle",
            ),
        ],
        is_stale_cache=False,
    )
    assert payload.contract_version == HEALTH_CONTRACT_VERSION
    product = next(s for s in payload.sources if s.source_id == "seiko_products")
    news = next(s for s in payload.sources if s.source_id == "monochrome_rss")
    # Both may report ZERO_ITEMS; overall is WARNING because product catalogue matters.
    assert product.status == SourceHealthStatus.ZERO_ITEMS
    assert news.status == SourceHealthStatus.ZERO_ITEMS
    assert payload.overall_status == OperationalState.WARNING


def test_health_cache_marked_stale() -> None:
    payload = HealthPayload(clank_id="oem-radar", overall_status=OperationalState.HEALTHY, is_stale_cache=True)
    assert payload.is_stale_cache is True


# --- Delivery status enum -----------------------------------------------------

def test_delivery_status_values() -> None:
    assert DeliveryStatus.DELIVERY_PENDING == "delivery_pending"
    assert DeliveryStatus.DELIVERY_FAILED_RETRYABLE == "delivery_failed_retryable"
