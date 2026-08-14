# Stage Roadmap v3

Revised after the Great Clank Audit. Minimises simultaneous risk.

| Stage | Focus | Exit criteria |
|-------|-------|---------------|
| **0 / 0.5** | Skeleton + architecture guardrails | Done (main) |
| **0.75** | Audit reconciliation, Architecture v3 contracts, tests | This branch |
| **1** | NAS deployment foundation, Docker/volumes, basic adapters, Fleet health read | Per-Clank NAS readiness gate green for first pilot |
| **1.5** | Cross-platform desktop connected mode + local cache schema live | Desktop starts usefully offline; live vs stale visible |
| **2** | Ledger + incidents + richer telemetry export | Ledger join keys stable; offline Ledger sync works |
| **2.5** | Fallback Level 1–2 for selected Clanks; fencing design verified | No split-brain in tests; Level 3 still gated |
| **3** | ClankOps (analysis layer) | Uses existing telemetry IDs; no ID redesign |
| **4** | Hermes (read/investigate) | Read surfaces only by default |

## Sequencing rules

1. Do not migrate production Clanks to NAS until Stage 1 gates pass per Clank.
2. Do not enable Level 3 fallback until fencing + failback drills pass.
3. Do not build ClankOps before telemetry and Ledger IDs are stable.
4. Prefer shallow adapters early over deep integration.
