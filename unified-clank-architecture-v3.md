# Unified Clank Architecture v3

> **Status:** Architecture reconciliation after the Great Clank Audit (2026-08-14)  
> **Supersedes (conceptually):** v2 / v2.1-reviewed for control-plane design  
> **Does not delete:** prior architecture documents remain historical  
> **Stage:** 0.75 — Audit reconciliation / contracts; **no deployment**

## 1. Goals

1. Provide a **control plane** (Fleet + Desktop + contracts) for the heterogeneous Clank army.
2. Encode Great Audit lessons as **versioned contracts**, not as forced internal rewrites.
3. Survive **NAS loss** via local-first desktop cache and explicit fallback levels.
4. Prevent **split-brain** production execution via ownership fencing.
5. Keep mature Clanks **independent runtimes** with their own collectors, identity, and SQLite schemas.

## 2. Non-goals

- Shared mega-runtime or monolith.
- Centralised product identity or source-specific health interpretation.
- ClankOps analytics or Hermes integration in this stage.
- Automatic promotion of sources.
- Deploying or migrating production Clanks to NAS in this phase.

## 3. Topology

```text
                         ┌──────────────────────────┐
                         │      CLANK DESKTOP       │
                         │ Windows / macOS / Linux  │
                         │ local-first + fallback   │
                         └────────────┬─────────────┘
                                      │ Fleet API / sync
                         ┌────────────▼─────────────┐
                         │         CLANK HQ         │
                         │          NAS             │
                         │ Fleet · Ledger · Telemetry│
                         │ Backups · (ClankOps later)│
                         └──────┬─────┬─────┬───────┘
                                │     │     │
                          independent Clank runtimes
```

NAS healthy → NAS is primary production environment.  
NAS unavailable → Desktop remains useful (cached state + safe offline writes + gated fallback).

## 4. First principle: unification ≠ homogenisation

OEM Radar is not Feature Phone Clank. Chinese Tech Wire is not Watch Clank.

Unified integrates via:

- behavioural / health / telemetry **contracts**
- **adapters** with explicit capabilities
- deployment manifests and backup contracts
- human-visible status and Ledger

Unified must **not** require rewrites of collectors, parsers, identity systems, SQLite schemas, classifiers, editorial logic, or source cadence.

## 5. Runtime vs control plane

| Layer | Owns | Does not own |
|-------|------|--------------|
| Individual Clank | collectors, parsers, identity, domain state, source health interpretation | Fleet API, desktop UI, army-wide Ledger |
| clank-runtime | versioned contracts, enums, fencing models, offline action classes | scraping, production DBs |
| clank-fleet | API shell, inventory, adapter orchestration (later) | domain logic |
| clank-desktop | local cache, offline queue, UI, machine capability | production Clank DBs |

## 6. Health contract

Fleet consumes **declared** source health (`ok`, `degraded`, `failed`, `blocked_zero`, `zero_items`, …).

Source-specific zero semantics remain Clank-owned:

- News/RSS empty cycle may be healthy `zero_items`.
- Product catalogue empty after prior success must not be reported as overall healthy (Watch Clank lesson).

Overall Clank status: `HEALTHY | WARNING | FAILED | STALE | UNKNOWN | PAUSED | EXPERIMENTAL`.

Desktop must set `is_stale_cache=true` when showing cached health.

## 7. Telemetry envelope

Versioned `TelemetryEnvelope` maps internal run/event tables via adapters.  
Stable `lead_id` + `source_url` enable later Ledger joins without ClankOps.

Baseline events are flagged (`is_baseline` / `run_kind=baseline_build`); they are not equivalent to new production alerts.

## 8. Delivery accounting

Fleet-facing statuses: `EVENT_CREATED`, `DELIVERY_PENDING`, `DELIVERY_SUCCEEDED`, `DELIVERY_FAILED_RETRYABLE`, `DELIVERY_FAILED_FINAL`, `DELIVERY_UNKNOWN`, suppressions.

OEM Radar outbox is a reference implementation pattern — not a forced shared library. Adapters report capability `supports_delivery_accounting`.

## 9. Source lifecycle & soak

States: `DISCOVERED → RESEARCH → EXPERIMENTAL → SOAK → PRODUCTION` (+ `DISABLED`, `QUARANTINED`).  
Allowed transitions are enforced at contract level. Promotion is always explicit.

Soak progress is displayable (cycles completed/required, failures, false events, promotion gate). Cadence determines requirements — no universal cycle count.

## 10. Failure taxonomy

Stable `FailureClass` enum from the Great Audit. Prefer `UNKNOWN` over false diagnosis.

## 11. Desktop local-first

Local SQLite **cache only** (schema versioned, replaceable). Never holds production Clank databases.

**Connected mode:** live Fleet API.  
**Fallback mode:** last-known fleet/source/incident summaries, local Ledger, offline queue, diagnostics, reconnection attempts. UI always distinguishes live vs cached.

## 12. Offline queue semantics

| Class | Examples | Reconnect behaviour |
|-------|----------|---------------------|
| SAFE_OFFLINE | Ledger HIT/MISS, notes | Auto-sync if idempotent |
| STALE_SENSITIVE | restart, pause, run_now | Draft only; reconfirm live |
| HIGH_RISK | deploy, restore, promote | Never auto-execute |
| READ_ONLY | status, logs | No queue needed |

**Never** fire a six-hour-old restart because NAS came back.

## 13. Machine capability model

Machines declare OS, Python/Docker, secrets readiness, supported Clank IDs, max fallback level.  
Desktop must not claim local fallback for a Clank the machine cannot run.

## 14. Fallback levels & fencing

| Level | Meaning |
|-------|---------|
| 0 | Observability only |
| 1 | Offline Ledger/cache |
| 2 | Read-only diagnostics + local probes |
| 3 | Full local execution — **requires ownership token** |

`can_start_fallback` refuses Level 3 when NAS status is uncertain (split-brain prevention). Ownership uses monotonic `epoch` + `OwnershipToken`. Failback: quiesce fallback → compare epochs → restore NAS primary → reconcile allowed events; do not assume arbitrary DB merge.

## 15. Adapter strategy

Shallow start: `identity`, `status`, `version`, optional `health`/`telemetry`.  
Later: `manual_run`, `pause`, `delivery_accounting`, `replay`, `fallback`.  
Unsupported operations raise `UnsupportedOperationError`; capabilities are explicit.

## 16. SQLite on NAS

Each production SQLite DB lives on a **local** volume from the process perspective (not SMB/NFS). WAL, one-writer, graceful shutdown, backup/restore tested. **No** shared fleet-wide SQLite for all Clanks.

## 17. Backups

| Tier | Content |
|------|---------|
| 1 | Code (GitHub) |
| 2 | Per-Clank state (SQLite + persistent data) |
| 3 | Unified control state (Fleet/Ledger/config) |
| 4 | Hermes state (later) |

Untested restores are not proven backups.

## 18. ClankOps & Hermes boundaries

Unified provides stable IDs, telemetry history, Ledger linkage, incident representation.  
ClankOps (later): analysis and recommendations.  
Hermes (later): read/investigate surfaces — not unrestricted production mutation.

## 19. Security

Private LAN/Tailscale scale. Distinguish READ / SAFE WRITE / OPERATIONAL / HIGH RISK. Offline mode must not weaken online auth assumptions.

## 20. Versioning

All inter-component contracts versioned independently (`TELEMETRY_CONTRACT_VERSION`, `ADAPTER_CONTRACT_VERSION`, …). Legacy adapters declare versions; no forced simultaneous upgrade.

## 21. Adoption

Existing Clanks join via adapters without collector/DB rewrites.  
Stage roadmap: see `STAGE_ROADMAP_V3.md`.  
NAS readiness and desktop fallback gates: see gate documents.
