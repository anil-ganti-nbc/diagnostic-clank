# Architecture Principles — Unified Clank

These principles govern every Stage after 0. They are derived from:

- `unified-clank-architecture-v2.md`
- `unified-clank-architecture-v2.1-reviewed.md`

When in conflict, the reviewed v2.1 amendments win.

## 1. Survival before platform

P0 work (Dockerized clanks, NAS, Tailscale, domain DB persistence, backup verification, health contract, minimal Fleet CLI) precedes central ingestion, Fleet API fullness, and Desktop.

Do not implement deferred platform features under the guise of “small helpers.”

## 2. Domain authority stays with clanks

Each clank owns its domain models and domain databases. The central platform never writes back into Layer A domain stores. Historical imports are one-way.

## 3. Contracts evolve independently

Package version ≠ API contract version ≠ runtime contract version ≠ event contract version.

Never conflate them. Bump only the contract that actually changed.

## 4. Interfaces before implementations

Stage 0 / 0.5 stop at Protocol / ABC / 501 boundaries. Concrete adapters appear only in the stage that owns them.

## 5. Producer-owned outboxes (when built)

Shared append-only JSONL is rejected. Each producer owns its spool under a bounded path. One writer per spool. Atomic rename. Quarantine. Checkpoint ledger.

Event adapters are **not** P0 (Amendment 5).

## 6. Confidence is multi-dimensional

Never collapse confidence into a single scalar. Dimensions include source reliability, evidence strength, corroboration, freshness, parser quality, ingestion quality, entity certainty.

## 7. Native desktop is a client, not a controller

Desktop talks only to the Fleet API. It does not mount NAS paths, open Docker sockets, or embed scrapers.

## 8. No public exposure by default

Tailscale mesh only. No public router ports. Compose templates must not publish wildcard binds without an explicit, documented warning.

## 9. Architecture tests are mandatory

Any PR that introduces SQLite/SQLAlchemy/Playwright/Selenium/Scrapy, Docker socket mounts, hardcoded secrets, Windows-only imports without adapters, or production logic inside Stage 0 placeholder modules must fail CI.

## 10. Smallest reversible change

When uncertain, choose the smallest reversible structure. Do not generalize prematurely. Do not add clever infrastructure.

## Directory ownership

| Path | Owns | Must not own |
|------|------|--------------|
| `clank-runtime` | Contracts, protocols, version constants | Scraping, collectors, domain models, business logic, persistence |
| `clank-fleet` | Fleet API shell, CLI, control interfaces, compose templates, inventory format | Domain scraping, central store schema, desktop UI |
| `clank-desktop` | Native UI shell | Direct NAS/Docker access, HTTP clients (until Stage 5), local domain DBs |

## Dependency rules

1. Runtime must not depend on Fleet or Desktop.
2. Fleet may depend on Runtime.
3. Desktop may depend on Runtime for shared types only; must not depend on Fleet implementation packages until a deliberate client stage.
4. No package may depend on an existing clank repository (oem-radar, watch-clank, etc.).
5. Forbidden in Stage 0 / 0.5 source: `sqlite3`, SQLAlchemy, Playwright, Selenium, Scrapy, Docker SDK with socket mounts.

## Coding standards (Stage 0.5)

- Python ≥ 3.11, `from __future__ import annotations`
- `pathlib.Path` only; no hardcoded `C:\` or Windows-only modules without an explicit platform adapter
- Ruff for lint/format; Pyright basic for types
- Pydantic v2 models for external contracts
- Operational stubs return explicit `STAGE0_NOT_IMPLEMENTED` / HTTP 501 / exit 78
- Docstrings must state Stage 0 / 0.5 limits where relevant
