# clank-runtime Architecture (Stage 0)

This package provides **draft contracts and interfaces only**.

It does not implement:

- event writing or outbox spools
- health checks
- operation execution
- logging backends
- retry policies
- schedulers
- heartbeat writers

## Authoritative references

- `unified-clank-architecture-v2.md`
- `unified-clank-architecture-v2.1-reviewed.md` (amendments take precedence)

Per Amendment 2, clank-runtime owns infrastructure concerns (logging, config, health contract, metadata, graceful shutdown, event contract helpers) and does **not** own scraping, collectors, domain models, or business logic.

## Contract versions

Contract versions evolve independently of the package version (`0.0.1.dev0`).

See `clank_runtime.version`.
