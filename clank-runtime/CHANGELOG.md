# Changelog — clank-runtime

## [0.0.1.dev0] — Stage 0.5

### Changed
- Stricter Pydantic models (`extra=forbid`, field constraints)
- `clank_id` pattern and reserved-name validation
- Confidence dimension constants (`contracts.confidence`)
- Explicit `STAGE 0.5 BOUNDARY` markers on protocol packages
- StrEnum for all contract enums

### Added
- Validation tests for reserved ids, extra fields, confidence constants

### Notes
Still no production behavior. Contracts remain draft (`*-stage0` versions).
