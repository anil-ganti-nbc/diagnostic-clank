# Fallback Fencing & Failback

## Problem

NAS recovers while desktop fallback still runs → two primaries → duplicate events and divergent state. Unacceptable.

## Ownership model

- Monotonic `epoch` per `clank_id`.
- `OwnershipToken` binds role (`nas_primary` | `desktop_fallback`), epoch, issuer, optional expiry.
- Level 3 execution requires valid desktop token **and** `nas_definitely_offline=true`.
- Uncertain NAS status → refuse Level 3 (`can_start_fallback`).

## Failback sequence

```text
NAS restored
  → detect higher/new NAS epoch or heartbeat
  → mark ownership CONTESTED or NAS_PRIMARY
  → quiesce desktop fallback (stop writers)
  → preserve fallback event/ledger output
  → restore canonical NAS state as primary
  → replay only validated observations where Clank supports replay
  → manual reconcile exceptions
```

Do not merge arbitrary SQLite files.

## Levels

Level 0–2 do not require fencing. Level 3 always does.
