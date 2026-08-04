# Contributing — Stage 0.5

## Before you write code

1. Read `ARCHITECTURE_PRINCIPLES.md`.
2. Read `DEPENDENCIES.md`.
3. Confirm your change does **not** implement Stage 1+ behavior.

## Rules for coding agents

- Prefer the smallest reversible change.
- Stop at Protocol / 501 / exit-78 boundaries.
- Do not add SQLite, SQLAlchemy, Playwright, Selenium, Scrapy, or Docker socket usage.
- Do not import existing clank repositories.
- Do not put production logic in modules marked `STAGE 0.5 BOUNDARY`.
- Do not add TODOs that describe implementing forbidden features.
- Run `make architecture` and `make check` before claiming done.

## Package ownership

| Package | May change | Must not absorb |
|---------|------------|-----------------|
| clank-runtime | contracts, protocols, version constants | scrapers, persistence, fleet API |
| clank-fleet | API shell, CLI, compose templates, inventory draft | domain collectors, desktop UI |
| clank-desktop | UI shell structure | HTTP clients, NAS, Docker |

## PR checklist

- [ ] Architecture tests pass
- [ ] No new runtime dependencies without updating `DEPENDENCIES.md`
- [ ] Docstrings state Stage 0.5 limits where relevant
- [ ] CHANGELOG updated under the package you touched
