# Production Delivery Contract

> Fleet-wide invariant. A Clank is not operational merely because its collectors run successfully.

## Purpose chain

```text
SOURCE → COLLECTION → PARSING → IDENTITY / NORMALIZATION → PERSISTENCE
  → STATE / FRESHNESS → EVENT / LEAD → ELIGIBILITY → NOTIFICATION / DELIVERY
```

A production-capable Clank must prove this chain for a qualifying real-world signal via its **exact unattended production entrypoint**.

## Two health domains

| Domain | Meaning |
|--------|---------|
| **Collection health** | Sources, parsing, persistence, run success |
| **Delivery health** | Editorial path, health-alert path, authority, secrets, webhook |

A Clank may report:

```text
COLLECTION: HEALTHY
DELIVERY: DEGRADED
RELEASE: DEGRADED
```

It must **never** collapse those into a single misleading `HEALTHY`.

### Release-state vocabulary (mandatory)

| State | Meaning |
|-------|---------|
| `HEALTHY` | Collection **and** delivery contract verified |
| `DEGRADED` | Core collection works; a required output path is unavailable |
| `PARTIAL` | Deployment exists; full production acceptance not passed |
| `FAILED` | Core collection/persistence path broken |
| `BASELINING` | Intentionally suppressing external intelligence while establishing state |

This vocabulary alone would have prevented Watch Clank looking “17/17 HEALTHY” while Discord was nonexistent.

## Production-path parity

Manual and scheduled production runs must use equivalent intelligence semantics. Scheduling may alter **when** work runs, not **what** counts as a new item, event, lead, alert, or qualifying transition.

Silent/baseline/validation modes must be **explicit**. Do not rely on hidden defaults (`emit_events=False`, `notify=False`) inside production paths.

## Modes

| Mode | Behaviour |
|------|-----------|
| `BASELINE` | Persist state; suppress historical floods; no newsroom alert storm |
| `VALIDATION` | Controlled testing; explicit notifier behaviour; no accidental side effects |
| `PRODUCTION` | Normal event/lead generation, eligibility, and notification |

Production semantics must never silently inherit baseline defaults.

## End-to-end acceptance

Every production-capable collector needs at least one E2E test:

production entrypoint → qualifying discovery → persisted state → event/lead → eligibility → **fake notifier invocation**

Companion regressions: baseline silent, stale silent, duplicate silent, below-threshold silent, notifier failure does not roll back collection, missing webhook safe/no-op, collector failure does not fabricate state.

## Configuration invariants

Impossible production configuration must fail loudly or degrade health:

- notifications enabled but webhook missing
- threshold > maximum attainable score
- authority without delivery target
- source enabled without scheduler
- scheduler without executable collector
- schema below required version

These must not present as fully `HEALTHY`.

## Delivery canary

Each Clank with external notification must support a safe canary that:

- exercises the **real** transport
- never fabricates a production Event
- never enters editorial intelligence history
- identifies itself as `TEST/CANARY`
- verifies delivery success

Cadence: daily or after deploy/config change. Prefer a dedicated ops/health destination if newsroom spam is undesirable.

## Deployment acceptance

Build/tests/migrations/timers green is not enough. **VERIFIED** requires:

- exact Git SHA verified
- schema at head
- DB integrity verified
- production scheduler exercised
- baseline protections verified
- delivery runtime sees configuration
- editorial test delivered
- health test delivered
- notification authority verified
- no duplicate sender
- no stale locks/runs
- repeat-run stability proven

Anything less is `PARTIAL` or `DEGRADED`.

## Single notification authority

Multiple hosts may collect. **Exactly one** host is authoritative for each external notification channel. Do not depend on distributed SQLite or cross-host dedup for notification correctness. Authority must be explicit and inspectable.

## Reproducibility / GitHub canonical

Portable implementation lives in GitHub. Fixes that exist only as untracked scripts, host-local edits, or one-off DB manipulation do not count. Fresh clone + documented secrets must reproduce the capability.

## Failure corpus / ClankBench

Material real-world misses become regression specimens. CI answers: **WOULD CURRENT CLANK CATCH THIS TODAY?** A previously fixed failure regressing to MISS should block promotion.

## Fleet rule

```text
GREEN COLLECTORS ARE NECESSARY.
GREEN DELIVERY IS MANDATORY.
```

## Code

- `clank_runtime.contracts.delivery` — models and `compose_release_state`
- `ClankReleaseState`, `CollectionHealthState`, `DeliveryHealthState`, `ProductionMode`
- Contract version: `DELIVERY_CONTRACT_VERSION`
