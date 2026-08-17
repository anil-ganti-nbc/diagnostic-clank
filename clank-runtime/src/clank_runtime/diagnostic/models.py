
"""Diagnostic case / stage / evidence / result models."""
from __future__ import annotations
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field

class IncidentType(StrEnum):
    MISS = "miss"
    FALSE_POSITIVE = "false_positive"
    STALE_ALERT = "stale_alert"
    FALSE_NOVELTY = "false_novelty"
    DUPLICATE_ALERT = "duplicate_alert"
    FALSE_REMOVAL = "false_removal"
    DELIVERY_FAILURE = "delivery_failure"
    LATENCY_FAILURE = "latency_failure"
    SOURCE_HEALTH_ANOMALY = "source_health_anomaly"
    INFRASTRUCTURE_ANOMALY = "infrastructure_anomaly"
    MANUAL_INVESTIGATION = "manual_investigation"

class StageId(StrEnum):
    SOURCE_CAPABILITY = "source_capability"
    REGION_COVERAGE = "region_coverage"
    DISCOVERY = "discovery"
    FETCH = "fetch"
    PARSE = "parse"
    EXTRACTION = "extraction"
    IDENTITY = "identity"
    BASELINE = "baseline"
    EPOCH = "epoch"
    TEMPORAL_RESOLUTION = "temporal_resolution"
    FRESHNESS = "freshness"
    PRODUCT_NOVELTY = "product_novelty"
    EVENT_NOVELTY = "event_novelty"
    PRIOR_COVERAGE = "prior_coverage"
    SCORING = "scoring"
    ATTENTION_CLASS = "attention_class"
    EVENT_CREATION = "event_creation"
    GUI_VISIBILITY = "gui_visibility"
    DELIVERY = "delivery"
    EXECUTION_PROVENANCE = "execution_provenance"
    INFRASTRUCTURE = "infrastructure"

class StageVerdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNSUPPORTED = "unsupported"

class DiagnosticConfidence(StrEnum):
    VERIFIED = "verified"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNRESOLVED = "unresolved"

class CausalRole(StrEnum):
    PRIMARY_ROOT_CAUSE = "primary_root_cause"
    DOWNSTREAM_CONSEQUENCE = "downstream_consequence"
    CONTRIBUTING_FACTOR = "contributing_factor"

class EvidenceType(StrEnum):
    TELEMETRY = "telemetry"
    SOURCE_HEALTH = "source_health"
    RAW_OBSERVATION = "raw_observation"
    PARSED_OBSERVATION = "parsed_observation"
    IDENTITY_RECORD = "identity_record"
    EVENT = "event"
    DELIVERY_RECORD = "delivery_record"
    LOG = "log"
    LEDGER_FEEDBACK = "ledger_feedback"
    GOLD_CASE = "gold_case"
    REPLAY_RESULT = "replay_result"
    PRODUCTION_EPOCH = "production_epoch"
    HISTORICAL_ARCHIVE = "historical_archive"
    BUILD_PROVENANCE = "build_provenance"
    AGENT_OUTPUT = "agent_output"
    MANUAL_NOTE = "manual_note"

class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_id: str = Field(default_factory=lambda: str(uuid4()))
    evidence_type: EvidenceType
    clank_id: str | None = None
    source_id: str | None = None
    run_id: str | None = None
    event_id: str | None = None
    ledger_id: str | None = None
    epoch_id: str | None = None
    timestamp: datetime | None = None
    uri: str | None = None
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class StageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: StageId
    verdict: StageVerdict
    notes: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)

class CausalFactor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: CausalRole
    failure_class: str
    summary: str

class DiagnosticCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime | None = None
    clank_id: str
    incident_type: IncidentType
    subject_entity: str | None = None
    source_url: str | None = None
    expected_event: str | None = None
    observed_event: str | None = None
    reported_by: str | None = None
    ledger_id: str | None = None
    gold_case_id: str | None = None
    investigation_status: str = "open"
    current_stage: StageId | None = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    stage_results: list[StageResult] = Field(default_factory=list)
    facts: dict[str, Any] = Field(default_factory=dict)
    unresolved_questions: list[str] = Field(default_factory=list)
    related_prior_cases: list[str] = Field(default_factory=list)
    related_agent_output_ids: list[str] = Field(default_factory=list)
    opened_at: datetime | None = None
    resolved_at: datetime | None = None
    extensions: dict[str, Any] = Field(default_factory=dict)

class DiagnosticResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str
    clank_id: str
    revision: int = 1
    supersedes: int | None = None
    status: str = "complete"
    first_failed_gate: StageId | None = None
    failure_class: str = "unknown"
    confidence: DiagnosticConfidence = DiagnosticConfidence.UNRESOLVED
    primary_root_cause: str | None = None
    contributing_factors: list[CausalFactor] = Field(default_factory=list)
    downstream_effects: list[CausalFactor] = Field(default_factory=list)
    evidence_used: list[str] = Field(default_factory=list)
    evidence_missing: list[str] = Field(default_factory=list)
    applicable_laws: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
    regression_fixture_recommendation: str | None = None
    suggested_fix: str | None = None
    human_summary: str = ""
    created_at: datetime | None = None

KNOWN_LESSONS = (
    "FIRST_SEEN_NOT_NEW", "BASELINE_NOT_NEWS", "OLD_FIRST_SEEN_URL_NOT_FRESH",
    "ABSENCE_NOT_NOVELTY", "REGION_ADDITION_NOT_NEW_IDENTITY", "DOCUMENT_TYPE_BEFORE_EVENT",
    "OPS_HEALTH_NOT_INTEL_HEALTH", "ONE_AUTHORITATIVE_WRITER", "CLAIM_RECORDED_NOT_TRUE",
    "DO_NOT_FIX_BEFORE_RECONSTRUCTING",
)
