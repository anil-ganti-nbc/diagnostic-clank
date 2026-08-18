# DiagnosticBench v0.1 — Design

**Lane:** curriculum / corpus / semantic fixtures only  
**Not:** runtime, GUI, SQLite, packaging (Claude/Codex)

## Purpose
Test that Diagnostic Clank (Archivist) can represent real historical Clank L’s without inventing root causes, deleting contradictions, or mutating raw evidence.

## Knowledge laws under test
- CLAIM_RECORDED ≠ CLAIM_TRUE
- LATEST_CLAIM ≠ AUTHORITATIVE_TRUTH
- DERIVED_KNOWLEDGE ≠ RAW_EVIDENCE
- RAW_EVIDENCE_IS_IMMUTABLE
- CONTRADICTION ≠ CORRUPTION
- FIRST_SEEN_BY_CLANK ≠ NEW_TO_MARKET
- BUILD_SUCCESS ≠ OWNER_FIELD_TEST_ACCEPTANCE
- LOCAL_WORKSPACE ≠ CANONICAL_FLEET_INVENTORY
- AUTOMATED_VERIFIED ≠ OWNER_ACCEPTED

## Semantic case schema (implementation-agnostic)
```yaml
case_id: L-OEM-001          # stable id
affected_clank: oem-radar   # registry id, not display string
period: "2026-08"           # or UNKNOWN
title: "..."
confidence: confirmed | partial | open | incomplete_evidence | suspected
status_expected: resolved | open | disputed | partial
classification_expected: [SCHEDULER_FAILURE, SOURCE_GAP, ...]
raw_evidence_required: [report hashes / source labels]
claims:
  - text: "..."
    authority_domain: owner_observation | agent_report | git | log | test
    expected_fate: retained | superseded | disputed
root_cause_expected: "..." | UNKNOWN   # never invent
fix_expected: "..." | none
lesson_expected: "..." | none
clankops_consequence_expected: "..." | none
provenance_must_link: true
search_queries: ["..."]
catastrophic_if:
  - invents_root_cause
  - deletes_prior_claim
  - mutates_raw_evidence
```

## Incident lifecycle (minimal)
OPEN → INVESTIGATING → PARTIAL → FIX_CANDIDATE → AUTOMATED_VERIFIED → OWNER_RETEST_PENDING → RESOLVED  
Also: REOPENED, DISPUTED  

**RESOLVED** requires evidence of fix *and* (for owner-facing paths) owner retest or explicit owner acceptance. Automated green alone is insufficient for native/launcher cases.

## Fix vs Lesson vs ClankOps Consequence
| Concept | Meaning |
|---------|---------|
| **Fix** | Concrete change applied (code/config/process step) |
| **Lesson** | What the failure taught about system behaviour |
| **ClankOps Consequence** | Standing rule / gate for future work |

These three must never collapse into one field.

## Evidence authority (by domain, not agent rank)
| Claim type | Stronger evidence |
|------------|-------------------|
| Owner clicked X and it failed | Owner observation |
| Test count / hash / integrity | Automated test / hash |
| Commit exists | Git history |
| Scheduler actually fired | Natural schedule log |
| Process behaviour | Runtime telemetry / logs |
| Hypothesis | Agent report (REPORTED until corroborated) |

Disagreement is allowed; supersession is explicit.

## Scoring dimensions (interpretable, not fake precision)
evidence preservation · attribution · classification · chronology · claim-history integrity · root-cause restraint · resolution linkage · provenance · retrieval · contradiction handling

**Catastrophic (auto-fail case):** invent root cause · delete conflict · wrong Clank attribution · mutate raw · claim resolved without evidence

## Seeding stages (owner GUI → Diagnostic Clank)
1. Simple resolved L → root cause → fix → verification  
2. Wrong prior agent claims later corrected  
3. Open / UNKNOWN root cause  
4. Architectural lessons (Fix ≠ Lesson ≠ Consequence)  
5. Messy multi-finding agent reports  
6. Contradictory multi-agent evidence  

**Stop-ship gates:** raw mutation, silent loss, fabricated root cause, provenance loss, contradiction deletion, destructive dedupe

## Historical corpus block (human + machine)
```
# ============================================================
L-XXX — TITLE
CLANK:
DATE / PERIOD:
DISCOVERED BY:
SEVERITY:
CLASSIFICATION:
CONFIDENCE:          # confirmed|partial|open|incomplete_evidence|suspected
WHAT HAPPENED:
EXPECTED BEHAVIOUR:
OBSERVED BEHAVIOUR:
INITIAL CLAIMS / ASSUMPTIONS:
ROOT CAUSE:          # UNKNOWN valid
EVIDENCE:
FIX:                 # none valid
VALIDATION:
REGRESSION PROTECTION:
STATUS:
LESSON:
CLANKOPS CONSEQUENCE:
RELATED Ls:
UNRESOLVED:
SOURCE REPORTS:
```
Mandatory: CLANK, TITLE, CONFIDENCE, WHAT HAPPENED, STATUS, SOURCE REPORTS  
UNKNOWN explicitly valid on ROOT CAUSE, FIX, period, many optionals.

## Source-research knowledge (not incidents)
Types: SOURCE_RESEARCH | SOURCE_DECISION | SOURCE_REJECTION | SOURCE_DEFERRED  
Ingest later only; design now for queries like “which Watch sources were rejected and why?”

## Multi-agent
| Agent | Role |
|-------|------|
| Claude | Engine, GUI, storage, macOS client |
| Codex | Hardening, packaging, tests, focused fixes |
| Grok | Bench design, historical analysis, corpus (this payload) |
| ChatGPT + Owner | Requirements, corpus construction, acceptance |

Common future record: **CLANKOPS_RECORD** (agent-neutral). All agent output = evidence with provenance.

## Merge plan (after Claude v0.1 merges)
1. Claude v0.1 known-good HEAD  
2. Rebase DiagnosticBench onto it  
3. Map semantic expectations → actual interfaces (do not rename architecture to match bench)  
4. Missing capabilities → IMPLEMENTATION REQUIREMENT only  
5. Separate DiagnosticBench PR  
6. Stop before bulk historical ingest  

## Production
Diagnostic implementation modified: **NO**  
Other Clanks / Hetzner / NAS: **NO**
