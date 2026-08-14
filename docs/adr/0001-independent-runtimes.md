# ADR 0001 — Clanks remain independent runtimes

## Decision

Each production Clank keeps its own process/container, collectors, and database.

## Why

Audit evidence shows divergent source types and hard-won local invariants. A monolith would amplify coupling risk.

## Consequences

Integration via adapters and contracts. No shared production schema.
