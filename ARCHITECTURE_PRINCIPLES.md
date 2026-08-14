# Architecture Principles — Unified Clank

Derived from architecture v2.1-reviewed **and** the Great Clank Audit / Architecture v3.

When in conflict: **v3 contracts and these principles** win for control-plane work; individual Clanks retain domain autonomy.

## 1. Survival before platform

NAS foundation, backups, health, and safe deployment precede ClankOps, Hermes, and rich desktop analytics.

## 2. Unification is not homogenisation

Existing Clanks do not rewrite collectors, identity, or SQLite schemas to join Fleet. Adapters + contracts only.

## 3. Version every external contract

Health, telemetry, adapter, Ledger, machine capability, fallback, and cache schemas carry independent versions.

## 4. Source-semantic health

Fleet consumes declared source health. Empty RSS ≠ empty product catalogue. Watch Clank ZERO_ITEMS lesson is permanent.

## 5. Desktop is a survivability layer

Local-first cache. Live vs stale always visible. Offline Ledger works. Stale operational actions never auto-fire on reconnect.

## 6. No split-brain

Level 3 fallback requires ownership fencing and definite NAS offline. Failback is explicit; no silent dual primary.

## 7. SQLite stays per-Clank and local

No fleet-wide shared production DB. NAS volumes local to the writer process.

## 8. Delivery is accountable

Fire-and-forget without tracking is forbidden on production alert paths. Capability may be limited until adapters mature.

## 9. Promotion is explicit

Source lifecycle transitions are gated; never auto-promote from one successful request.

## 10. ClankOps and Hermes are later

Stable IDs and read surfaces now; analysis and investigation agents later. Prefer read over mutate for future agents.

## 11. Stage discipline

No jumping to deployment or production GUI polish before contracts and gates. Architecture tests enforce boundaries.

## 12. Prefer UNKNOWN to a false diagnosis

Failure taxonomy includes UNKNOWN. Do not force inaccurate classification.

## 13. Green collectors are necessary; green delivery is mandatory

Collection health and delivery health are separate domains. Release state
HEALTHY requires both, plus verified deployment acceptance. See
PRODUCTION_DELIVERY_CONTRACT.md and ADR 0007.
