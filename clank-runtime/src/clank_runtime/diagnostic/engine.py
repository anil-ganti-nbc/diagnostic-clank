"""Deterministic diagnostic reasoner — no LLM required."""
from __future__ import annotations
from datetime import UTC, datetime
from clank_runtime.diagnostic.models import (
    CausalFactor, CausalRole, DiagnosticCase, DiagnosticConfidence,
    DiagnosticResult, StageId, StageResult, StageVerdict,
)

PIPELINE_ORDER = [
    StageId.SOURCE_CAPABILITY, StageId.REGION_COVERAGE, StageId.DISCOVERY, StageId.FETCH,
    StageId.PARSE, StageId.EXTRACTION, StageId.IDENTITY, StageId.BASELINE, StageId.EPOCH,
    StageId.TEMPORAL_RESOLUTION, StageId.FRESHNESS, StageId.PRODUCT_NOVELTY, StageId.EVENT_NOVELTY,
    StageId.PRIOR_COVERAGE, StageId.SCORING, StageId.ATTENTION_CLASS, StageId.EVENT_CREATION,
    StageId.GUI_VISIBILITY, StageId.DELIVERY, StageId.EXECUTION_PROVENANCE, StageId.INFRASTRUCTURE,
]
_STAGE_TO_FAILURE = {
    StageId.SOURCE_CAPABILITY: "source_gap", StageId.REGION_COVERAGE: "region_gap",
    StageId.DISCOVERY: "discovery_failure", StageId.FETCH: "fetch_failure",
    StageId.PARSE: "parser_failure", StageId.EXTRACTION: "extraction_failure",
    StageId.IDENTITY: "identity_failure", StageId.BASELINE: "baseline_failure",
    StageId.FRESHNESS: "freshness_failure", StageId.PRODUCT_NOVELTY: "novelty_failure",
    StageId.EVENT_NOVELTY: "novelty_failure", StageId.PRIOR_COVERAGE: "prior_coverage_failure",
    StageId.EVENT_CREATION: "event_failure", StageId.DELIVERY: "delivery_failure",
    StageId.EXECUTION_PROVENANCE: "infrastructure_failure", StageId.INFRASTRUCTURE: "infrastructure_failure",
}

def _evaluate_stages(case: DiagnosticCase) -> list[StageResult]:
    f = case.facts
    results: list[StageResult] = []
    def add(stage: StageId, verdict: StageVerdict, notes: str | None = None) -> None:
        results.append(StageResult(stage=stage, verdict=verdict, notes=notes))
    if "source_capable" not in f:
        add(StageId.SOURCE_CAPABILITY, StageVerdict.INSUFFICIENT_EVIDENCE)
    elif f["source_capable"] is False:
        add(StageId.SOURCE_CAPABILITY, StageVerdict.FAIL, "no monitored source could expose evidence")
    else:
        add(StageId.SOURCE_CAPABILITY, StageVerdict.PASS)
    if "region_monitored" not in f:
        add(StageId.REGION_COVERAGE, StageVerdict.INSUFFICIENT_EVIDENCE)
    elif f["region_monitored"] is False:
        add(StageId.REGION_COVERAGE, StageVerdict.FAIL, "region/surface not monitored")
    else:
        add(StageId.REGION_COVERAGE, StageVerdict.PASS)
    for stage, key, note in [
        (StageId.DISCOVERY, "discovered", "evidence never discovered"),
        (StageId.FETCH, "fetch_ok", "fetch failed"),
        (StageId.PARSE, "parse_ok", "parse failed"),
        (StageId.EXTRACTION, "extraction_ok", "expected fields not extracted"),
        (StageId.IDENTITY, "identity_ok", "identity unresolved"),
    ]:
        if key not in f:
            add(stage, StageVerdict.INSUFFICIENT_EVIDENCE)
        elif f[key] is False:
            add(stage, StageVerdict.FAIL, note)
        else:
            add(stage, StageVerdict.PASS)
    if f.get("in_baseline_mode") is True:
        add(StageId.BASELINE, StageVerdict.PASS, "baseline mode active")
    elif "in_baseline_mode" in f:
        add(StageId.BASELINE, StageVerdict.PASS)
    else:
        add(StageId.BASELINE, StageVerdict.INSUFFICIENT_EVIDENCE)
    add(StageId.EPOCH, StageVerdict.PASS if ("epoch_id" in f or "epoch_boundary" in f) else StageVerdict.INSUFFICIENT_EVIDENCE)
    pub, seen = f.get("published_at"), f.get("first_seen_at")
    if pub is not None and seen is not None and hasattr(pub, "timestamp") and hasattr(seen, "timestamp"):
        age_days = (seen - pub).total_seconds() / 86400.0
        if age_days > 30 and not f.get("independent_fresh_event"):
            add(StageId.FRESHNESS, StageVerdict.FAIL, f"document age at discovery ~{age_days:.0f}d")
        else:
            add(StageId.FRESHNESS, StageVerdict.PASS)
    elif "freshness_ok" in f:
        add(StageId.FRESHNESS, StageVerdict.PASS if f["freshness_ok"] else StageVerdict.FAIL)
    else:
        add(StageId.FRESHNESS, StageVerdict.INSUFFICIENT_EVIDENCE)
    if f.get("novelty_from_absence_only") is True:
        add(StageId.PRODUCT_NOVELTY, StageVerdict.FAIL, "ABSENCE_TREATED_AS_POSITIVE_NOVELTY")
    elif f.get("first_seen_only") is True and f.get("new_to_market") is True:
        add(StageId.PRODUCT_NOVELTY, StageVerdict.FAIL, "FIRST_SEEN treated as NEW_TO_MARKET")
    elif "novelty_ok" in f:
        add(StageId.PRODUCT_NOVELTY, StageVerdict.PASS if f["novelty_ok"] else StageVerdict.FAIL)
    else:
        add(StageId.PRODUCT_NOVELTY, StageVerdict.INSUFFICIENT_EVIDENCE)
    if "event_novelty_ok" in f:
        add(StageId.EVENT_NOVELTY, StageVerdict.PASS if f["event_novelty_ok"] else StageVerdict.FAIL)
    else:
        add(StageId.EVENT_NOVELTY, StageVerdict.INSUFFICIENT_EVIDENCE)
    pc = f.get("prior_coverage")
    if pc is None:
        add(StageId.PRIOR_COVERAGE, StageVerdict.INSUFFICIENT_EVIDENCE)
    elif pc in {"SAME_EVENT", "same_event"}:
        add(StageId.PRIOR_COVERAGE, StageVerdict.FAIL, "exact event already covered")
    else:
        add(StageId.PRIOR_COVERAGE, StageVerdict.PASS, str(pc))
    if "event_created" not in f:
        add(StageId.EVENT_CREATION, StageVerdict.INSUFFICIENT_EVIDENCE)
    elif f["event_created"] is False:
        add(StageId.EVENT_CREATION, StageVerdict.FAIL)
    else:
        add(StageId.EVENT_CREATION, StageVerdict.PASS)
    if "delivery_ok" not in f and "delivery_observed" not in f:
        add(StageId.DELIVERY, StageVerdict.INSUFFICIENT_EVIDENCE,
            "LIMITED delivery visibility" if f.get("delivery_visibility") == "LIMITED" else None)
    elif f.get("delivery_ok") is False:
        add(StageId.DELIVERY, StageVerdict.FAIL, "delivery failed after event")
    elif f.get("delivery_ok") is True:
        add(StageId.DELIVERY, StageVerdict.PASS)
    else:
        add(StageId.DELIVERY, StageVerdict.INSUFFICIENT_EVIDENCE)
    if f.get("execution_integrity_ok") is False:
        add(StageId.EXECUTION_PROVENANCE, StageVerdict.FAIL, "competing writers or stale executable")
    elif "execution_integrity_ok" in f:
        add(StageId.EXECUTION_PROVENANCE, StageVerdict.PASS)
    else:
        add(StageId.EXECUTION_PROVENANCE, StageVerdict.INSUFFICIENT_EVIDENCE)
    if f.get("infra_ok") is False:
        add(StageId.INFRASTRUCTURE, StageVerdict.FAIL, f.get("infra_note", "infrastructure failure"))
    elif "infra_ok" in f:
        add(StageId.INFRASTRUCTURE, StageVerdict.PASS)
    else:
        add(StageId.INFRASTRUCTURE, StageVerdict.INSUFFICIENT_EVIDENCE)
    seen_s = {r.stage for r in results}
    for stage in PIPELINE_ORDER:
        if stage not in seen_s:
            results.append(StageResult(stage=stage, verdict=StageVerdict.INSUFFICIENT_EVIDENCE))
    order = {s: i for i, s in enumerate(PIPELINE_ORDER)}
    results.sort(key=lambda r: order.get(r.stage, 999))
    return results

class DeterministicReasoner:
    def diagnose(self, case: DiagnosticCase) -> DiagnosticResult:
        stages = _evaluate_stages(case)
        case.stage_results = stages
        failed = next((r for r in stages if r.verdict == StageVerdict.FAIL), None)
        laws = ["DO_NOT_FIX_BEFORE_RECONSTRUCTING"]
        missing = [r.stage.value for r in stages if r.verdict in {StageVerdict.INSUFFICIENT_EVIDENCE, StageVerdict.UNKNOWN}]
        if failed is None:
            if any(r.verdict == StageVerdict.INSUFFICIENT_EVIDENCE for r in stages):
                return DiagnosticResult(
                    case_id=case.case_id, clank_id=case.clank_id, status="unresolved",
                    failure_class="unknown", confidence=DiagnosticConfidence.UNRESOLVED,
                    evidence_missing=missing, applicable_laws=laws,
                    human_summary=f"Insufficient evidence to diagnose {case.incident_type.value} for {case.clank_id}.",
                    recommended_next_steps=["gather stage evidence", "attach agent outputs or telemetry"],
                    created_at=datetime.now(UTC),
                )
            return DiagnosticResult(case_id=case.case_id, clank_id=case.clank_id, status="complete",
                                    failure_class="unknown", confidence=DiagnosticConfidence.LOW,
                                    human_summary="No failed gate identified.", created_at=datetime.now(UTC))
        failure_class = _STAGE_TO_FAILURE.get(failed.stage, "unknown")
        if failed.stage == StageId.FRESHNESS:
            laws += ["OLD_FIRST_SEEN_URL_NOT_FRESH", "BASELINE_NOT_NEWS"]
        if failed.stage == StageId.PRODUCT_NOVELTY:
            laws += ["FIRST_SEEN_NOT_NEW", "ABSENCE_NOT_NOVELTY"]
        if failed.stage == StageId.REGION_COVERAGE:
            laws.append("REGION_ADDITION_NOT_NEW_IDENTITY")
        if failed.stage == StageId.SOURCE_CAPABILITY:
            laws.append("OPS_HEALTH_NOT_INTEL_HEALTH")
        downstream, past = [], False
        for r in stages:
            if r.stage == failed.stage:
                past = True
                continue
            if past and r.verdict == StageVerdict.FAIL:
                downstream.append(CausalFactor(role=CausalRole.DOWNSTREAM_CONSEQUENCE,
                    failure_class=_STAGE_TO_FAILURE.get(r.stage, "unknown"), summary=r.notes or r.stage.value))
        steps = ["Do not apply a fix until reconstruction is accepted", f"Investigate stage: {failed.stage.value}"]
        regression = suggested = None
        if failure_class == "extraction_failure":
            suggested, regression = "Extend extractor for missing field class (advisory only)", "Add fixture proving identity/SKU extraction"
            steps.append("Add regression fixture before coding")
        elif failure_class == "source_gap":
            suggested, regression = "Evaluate experimental source surfaces (advisory only)", "Gold case: MUST_ALERT when source becomes capable"
        elif failure_class == "freshness_failure":
            suggested, regression = "Enforce freshness/historical firewall", "MUST_NOT_ALERT for old documents without fresh event"
        elif failure_class == "delivery_failure":
            suggested, regression = "Inspect outbox/retry path (advisory)", "Delivery accounting conformance test"
        elif failure_class == "region_gap":
            suggested, regression = "Register region/surface coverage explicitly", "Brand×region×surface health must not greenwash"
        summary = (f"{case.clank_id} {case.incident_type.value}: first failed gate {failed.stage.value} → {failure_class}. "
                   f"{failed.notes or ''} Downstream: {len(downstream)}. Suggested fix is advisory only — Diagnostic Clank will not apply it.")
        return DiagnosticResult(
            case_id=case.case_id, clank_id=case.clank_id, status="complete",
            first_failed_gate=failed.stage, failure_class=failure_class,
            confidence=DiagnosticConfidence.HIGH,
            primary_root_cause=f"{failure_class}: {failed.notes or failed.stage.value}",
            downstream_effects=downstream, evidence_used=[e.evidence_id for e in case.evidence_refs],
            evidence_missing=missing, applicable_laws=laws, recommended_next_steps=steps,
            regression_fixture_recommendation=regression, suggested_fix=suggested,
            human_summary=summary.strip(), created_at=datetime.now(UTC),
        )

def diagnose(case: DiagnosticCase) -> DiagnosticResult:
    return DeterministicReasoner().diagnose(case)
