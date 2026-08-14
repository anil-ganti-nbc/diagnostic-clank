# ADR 0007 — Dual-domain health (collection vs delivery)

## Context

Watch Clank (and similar) could report all collectors healthy while the Discord delivery path was missing or misconfigured. Operators saw a green fleet with no newsroom output.

## Decision

1. Collection health and delivery health are **separate** reported domains.
2. Fleet release state `HEALTHY` requires **both** domains healthy **and** deployment acceptance `VERIFIED`.
3. Collection healthy + delivery missing/degraded ⇒ release state `DEGRADED` (or `PARTIAL` if acceptance incomplete), never `HEALTHY`.

## Consequences

Adapters and Clanks must expose both domains. Dashboards must not collapse them. Configuration invariants (webhook missing while notifications enabled) degrade delivery health loudly.
