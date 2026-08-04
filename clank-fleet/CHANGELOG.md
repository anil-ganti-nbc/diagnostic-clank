# Changelog — clank-fleet

## [0.0.1.dev0] — Stage 0.5

### Changed
- Consistent NotImplementedResponse on all 501 routes
- Richer OpenAPI summaries stating Stage 0.5 limits
- CLI error envelope includes api_contract_version and clank_id
- Expanded architecture guardrail tests

### Added
- Root-level Makefile targets consumed via monorepo layout
- Stronger compose template assertions (no docker.sock, no /volume1)

### Notes
Operational commands still exit 78. No Docker/SSH/HTTP control plane.
