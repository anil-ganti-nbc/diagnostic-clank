# DiagnosticBench v0.1 Design

**Lane:** Grok — curriculum / corpus / semantic fixtures  
**Not:** implementation, GUI, SQLite schema, packaging  
**Integration target:** Diagnostic Clank (Claude v0.1 first, then Codex harden)

---

## 0. Workspace

| Field | Value |
|-------|--------|
| Repository/worktree | ProjectClankOps **staging artifact** (not Claude's active Diagnostic Clank tree) |
| Path | `artifacts/diagnosticbench/` |
| Branch | N/A (payload for post-Claude integration) |
| Starting SHA | N/A |
| Files/directories touched | `artifacts/diagnosticbench/**` only |
| Claude implementation files touched | **NO** |

---

## 1. Purpose

DiagnosticBench is the **curriculum**, not the engine.

| Layer | Owner lane | Role |
|-------|------------|------|
| Diagnostic Clank | Claude → Codex | Engine: preserve, index, query, represent |
| DiagnosticBench | Grok (this) | Cases, expected outcomes, seeding protocol |
| Historical L corpus | ChatGPT + owner | Evidence wall-of-text + provenance |
| ClankOps | Shared | Process / laws |
| Motherclank | Shared | Future host |

Bench defines **what knowledge must be representable**, not how SQLite tables are named.

---

## 2. Knowledge laws under test

Every case must be constructible so that a correct Archivist:

| Law | Bench implication |
|-----|-------------------|
| CLAIM_RECORDED ≠ CLAIM_TRUE | Agent "FIELD-TEST READY" remains a claim |
| LATEST_CLAIM ≠ AUTHORITATIVE_TRUTH | Owner disproof does not delete prior claim |
| DERIVED ≠ RAW | Re-index cannot mutate raw report body/hash |
| RAW_EVIDENCE_IS_IMMUTABLE | Duplicate ingest does not rewrite body |
| CONTRADICTION ≠ CORRUPTION | Both claims retained; contradiction explicit |
| FIRST_SEEN ≠ NEW_TO_MARKET | Baseline/historical discovery ≠ market novelty |
| BUILD_SUCCESS ≠ OWNER_FIELD_TEST_ACCEPTANCE | Packaging green ≠ owner launcher works |
| LOCAL_WORKSPACE ≠ CANONICAL_FLEET_INVENTORY | Directory sweep ≠ fleet membership |

---

## 3. Benchmark case schema (semantic)

```yaml
case_id: DB-001                    # stable string
title: short human title
affected_clank: oem-radar          # registry id when known; else explicit string
related_clanks: []                 # optional
period: "2026-08"                  # or unknown
incident_family: scheduler_verification  # free taxonomy tag

evidence_status:                   # honesty gate
  # CONFIRMED_L_CONFIRMED_FIX
  # CONFIRMED_L_PARTIAL_FIX
  # CONFIRMED_L_OPEN
  # HISTORICAL_L_INCOMPLETE_EVIDENCE
  # SUSPECTED_L_DO_NOT_TREAT_AS_FACT

confidence: high | medium | low | unresolved

raw_evidence_requirements:
  - kind: agent_report | owner_note | log_excerpt | audit_excerpt | test_result
    source_agent: owner | claude | codex | grok | system | unknown
    must_preserve_verbatim: true
    notes: ...

expected:
  classification: []               # e.g. SCHEDULER_CONFIGURATION_FAILURE
  status: OPEN | INVESTIGATING | PARTIAL | RESOLVED | DISPUTED | ...
  root_cause:                      # string or UNKNOWN
  root_cause_must_not_be_invented: true
  preserves_original_claim: true
  preserves_superseding_claim: true
  preserves_contradiction: true
  resolution_linked: true | false | n/a
  lesson_linked: true | false | n/a
  provenance_required: true

claims:
  - id: claim-a
    text: "..."
    authority_domain: agent_assertion | owner_observation | automated_test | git | scheduler_log
    expected_fate: retained | superseded | disputed

fix:                             # optional; distinct from lesson
lesson:                            # optional
clankops_consequence:              # optional

relationships:
  - type: EXPLICIT                 # only EXPLICIT required for v0.1 seeding
    related_case_id: DB-00X
    note: ...

search_should_find:
  - query: "..."
    must_include_case: true

unresolved_questions: []
sources_surveyed: []               # paths/report titles used to define case
