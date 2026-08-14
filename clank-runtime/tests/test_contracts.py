"""Serialization and validation tests for Stage 0.5 runtime contracts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from clank_runtime.contracts.confidence import (
    KNOWN_CONFIDENCE_DIMENSIONS,
    SOURCE_RELIABILITY,
)
from clank_runtime.contracts.enums import (
    IngestionState,
    OperationalState,
    ReleaseChannel,
)
from clank_runtime.contracts.events import EventEnvelope
from clank_runtime.contracts.health import HealthPayload
from clank_runtime.contracts.identity import RuntimeIdentity
from clank_runtime.contracts.operations import (
    OperationResult,
    OperationState,
    OperationType,
)
from clank_runtime.version import (
    EVENT_CONTRACT_VERSION,
    HEALTH_CONTRACT_VERSION,
    OPERATION_CONTRACT_VERSION,
    RUNTIME_CONTRACT_VERSION,
    __version__,
)


def test_package_version() -> None:
    assert __version__ == "0.1.0.dev0"


def test_runtime_identity_roundtrip() -> None:
    identity = RuntimeIdentity(
        runtime_version="0.0.1.dev0",
        clank_id="example-clank",
        clank_version="0.1.0",
        release_channel=ReleaseChannel.EXPERIMENTAL,
    )
    data = identity.model_dump()
    restored = RuntimeIdentity.model_validate(data)
    assert restored.clank_id == "example-clank"
    assert restored.contract_version == RUNTIME_CONTRACT_VERSION
    assert restored.release_channel == ReleaseChannel.EXPERIMENTAL


def test_runtime_identity_rejects_empty_and_reserved() -> None:
    with pytest.raises(ValidationError):
        RuntimeIdentity(
            runtime_version="0.0.1",
            clank_id="",
            clank_version="0.1.0",
            release_channel=ReleaseChannel.PRODUCTION,
        )
    with pytest.raises(ValidationError):
        RuntimeIdentity(
            runtime_version="0.0.1",
            clank_id="fleet",
            clank_version="0.1.0",
            release_channel=ReleaseChannel.PRODUCTION,
        )
    with pytest.raises(ValidationError):
        RuntimeIdentity(
            runtime_version="0.0.1",
            clank_id="OEM_Radar",
            clank_version="0.1.0",
            release_channel=ReleaseChannel.PRODUCTION,
        )


def test_runtime_identity_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        RuntimeIdentity.model_validate(
            {
                "runtime_version": "0.0.1",
                "clank_id": "example-clank",
                "clank_version": "0.1.0",
                "release_channel": "experimental",
                "unexpected": True,
            }
        )


def test_health_payload_defaults() -> None:
    payload = HealthPayload(clank_id="example-clank")
    assert payload.contract_version == HEALTH_CONTRACT_VERSION
    assert payload.overall_status == OperationalState.UNKNOWN
    assert payload.is_stale_cache is False
    data = payload.model_dump()
    restored = HealthPayload.model_validate(data)
    assert restored.overall_status == OperationalState.UNKNOWN
    assert restored.clank_id == "example-clank"


def test_operation_result_not_implemented() -> None:
    result = OperationResult(
        operation_id="op-001",
        operation_type=OperationType.STATUS,
        state=OperationState.NOT_IMPLEMENTED,
        message="Not implemented in Stage 0",
        error_code="STAGE0_NOT_IMPLEMENTED",
    )
    assert result.contract_version == OPERATION_CONTRACT_VERSION
    data = result.model_dump()
    restored = OperationResult.model_validate(data)
    assert restored.state == OperationState.NOT_IMPLEMENTED


def test_event_envelope_roundtrip() -> None:
    now = datetime.now(UTC)
    event = EventEnvelope(
        event_id="evt-001",
        producer="example-clank",
        schema_name="product_change",
        schema_version="1",
        occurred_at=now,
        observed_at=now,
        confidence_dimensions={
            SOURCE_RELIABILITY: 0.9,
            "evidence_strength": 0.8,
        },
        payload={"sku": "X1"},
        payload_hash="abc123",
    )
    assert event.contract_version == EVENT_CONTRACT_VERSION
    data = event.model_dump(mode="json")
    restored = EventEnvelope.model_validate(data)
    assert restored.event_id == "evt-001"
    assert restored.confidence_dimensions[SOURCE_RELIABILITY] == 0.9


def test_confidence_dimension_constants() -> None:
    assert SOURCE_RELIABILITY in KNOWN_CONFIDENCE_DIMENSIONS
    assert len(KNOWN_CONFIDENCE_DIMENSIONS) >= 7


def test_enums_are_str() -> None:
    assert OperationalState.HEALTHY.value == "healthy"
    assert ReleaseChannel.PRODUCTION.value == "production"
    assert IngestionState.CURRENT.value == "current"
