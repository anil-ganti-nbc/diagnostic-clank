# ADR 0003 — Desktop local-first cache

## Decision

Desktop maintains a replaceable SQLite cache separate from production Clank DBs.

## Consequences

Useful offline UI; corrupt cache cannot corrupt Fleet production state.
