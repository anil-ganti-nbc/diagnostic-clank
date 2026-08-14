# Stage 1A Implementation

**Branch:** `unified-stage1a-2026-08`  
**Goal:** Fleet foundation + two real read-only adapters (OEM Radar, Feature Phone Clank).

## What was built

- `FleetRegistry` with isolation (`safe_status` / `safe_health` / …)
- `OemRadarAdapter` — RO SQLite (`crawler_runs`, optional `notification_outbox`)
- `FeaturePhoneAdapter` — RO SQLite (`collector_runs`), maps `blocked_zero_result`
- API: `GET /api/v1/clanks`, `/{id}`, `/health`, `/telemetry`, `/sources`, `/fleet/summary`
- CLI: `clank fleet list|status|health|telemetry`
- Fixtures + integration tests (26 fleet tests total)

## Explicit non-goals completed as non-goals

No NAS deploy, no production writes, no Discord, no collector runs, no ClankOps, no desktop polish, no merge to main.
