# Legacy Adapter Guide

## Goal

Join an existing Clank without rewriting collectors or DB schema.

## Phase A — shallow

Implement:

- `identity()` → `AdapterDescriptor`
- `status()` → `AdapterStatus`
- `capabilities()` → mostly false flags
- optional file/JSONL telemetry export mapped to `TelemetryEnvelope`

## Phase B — health

Map internal run status to `SourceHealthStatus`. Preserve source-semantic zeros.

## Phase C — control

Only after capability flags true: `manual_run`, `pause`, etc. Raise `UnsupportedOperationError` otherwise.

## Phase D — delivery / fallback

Map outbox or delivery table to `DeliveryStatus`. Declare `max_fallback_level` honestly.

## Anti-patterns

- Importing Unified into the Clank’s hot collector path as a hard dependency for parsing.
- Claiming `supports_local_fallback=true` without fencing and failback docs.
- Reinterpreting another Clank’s zero semantics in the adapter.
