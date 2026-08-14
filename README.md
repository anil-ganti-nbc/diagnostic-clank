# Unified Clank Platform

> **Status:** Stage 0.75 — Architecture v3 contracts after the Great Clank Audit  
> **No production behaviour. No deployment. No merge to main without review.**

Control plane, reference contracts, and survivability layer for the heterogeneous Clank army.

```
unified-clank-platform/
├── clank-runtime/     # versioned contracts (health, telemetry, adapter, fallback, …)
├── clank-fleet/       # Fleet API shell, CLI, inventories
├── clank-desktop/     # PySide6 shell (local-first cache designed, not full GUI)
├── unified-clank-architecture-v3.md
├── STAGE_ROADMAP_V3.md
├── AUDIT_RECONCILIATION.md
├── STANDARD_TRACEABILITY.md
├── NAS_STAGE1_DESIGN.md
├── DESKTOP_FALLBACK_DESIGN.md
├── FALLBACK_FENCING.md
├── LEGACY_ADAPTER_GUIDE.md
├── NAS_READINESS_GATE.md
├── DESKTOP_FALLBACK_GATE.md
└── docs/
```

## Read first

1. `unified-clank-architecture-v3.md` — authoritative control-plane architecture  
2. `ARCHITECTURE_PRINCIPLES.md` — rules every agent must follow  
3. `AUDIT_RECONCILIATION.md` — how the Great Audit maps into contracts  
4. `STANDARD_TRACEABILITY.md` — MUST items → ownership → tests  
5. `LEGACY_ADAPTER_GUIDE.md` — how existing Clanks join without rewrites  

## Bootstrap

```bash
make bootstrap
make check
```

## What works (Stage 0.75)

| Surface | Behaviour |
|---------|-----------|
| Runtime contracts | Validate/serialise health, telemetry, lifecycle, adapter, machine, fallback fencing, offline queue, Ledger |
| Contract tests | Round-trips, transition rules, fencing gates, stale-action safety |
| `GET /api/v1/system/ping` | 200 — process shell only |
| Other Fleet routes | 501 `STAGE0_NOT_IMPLEMENTED` |
| Desktop | Window shell; cache schema defined in contracts, not production-wired |
| Architecture guardrails | No production scrapers, no existing-clank imports, no secrets |

## What must never appear yet

Production scrapers, live NAS paths, real auth, production DB mutation, Hermes/ClankOps analytics, automatic execution of stale offline operations, split-brain fallback without fencing.

## Stages

See `STAGE_ROADMAP_V3.md`. Current branch target: **0.75**.

## License

MIT — see `LICENSE`.
