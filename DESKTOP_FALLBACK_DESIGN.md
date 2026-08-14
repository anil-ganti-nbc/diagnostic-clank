# Desktop Fallback Design

## Modes

**Connected:** Fleet API reachable; UI prefers live data; cache updated in background.  
**Fallback:** HQ unreachable; UI shows last-known state with explicit **stale** markers; safe offline writes queued.

## Local database

Schema: `clank_runtime.contracts.desktop_cache.DESKTOP_CACHE_DDL`.  
Replaceable, versioned (`CACHE_SCHEMA_VERSION`). Corrupt cache → delete and resync; never touches production Clank DBs.

## Surfaces (information architecture)

1. **Fleet** — per-Clank status, last run, location (NAS / local / unavailable), live vs cached.
2. **Sources** — lifecycle, health, soak, observed counts.
3. **Incidents** — unhealthy zeros, delivery failures, annotations.
4. **Ledger** — fast HIT/MISS (works offline).
5. **Operations** — connected + permitted only; stale-sensitive gated.
6. **Fallback** — HQ availability, machine capability, ownership, local controls.
7. **Intelligence** — reserved for ClankOps (empty until data exists).

## GUI principles

Dense operational UI. Obvious live vs cached. Keyboard usable. No decorative sludge. Status not colour-only. Starts usefully when HQ is dead.

## Offline queue

See `ActionSafetyClass`. Ledger entries: SAFE_OFFLINE + auto_sync. Restart/deploy: reconfirm after live restore.
