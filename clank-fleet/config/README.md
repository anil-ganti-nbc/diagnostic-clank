# Configuration conventions (Stage 0)

## Environment variable naming

- Prefix: `CLANK_`
- Area: `FLEET`, `RUNTIME`, `DESKTOP`, `INGESTION`, etc.
- Setting: uppercase with underscores

Example: `CLANK_FLEET_API_HOST`

## Path conventions

- Prefer `pathlib.Path`
- No hard-coded Windows drive letters (`C:\`) in source
- Document platform-specific defaults in later stages

## Secrets

- No real secrets in Stage 0
- `.env.example` contains only placeholders
- Production secret handling is deferred
