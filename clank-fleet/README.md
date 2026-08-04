# clank-fleet

Fleet control plane shell, API, and CLI for the Unified Clank Infrastructure.

**Stage 0.5 — skeleton + hardening. No production behavior.**

## Layout

```
src/clank_fleet/
  fleet_api/     # FastAPI factory + 501 route stubs
  operations/    # FleetControlAdapter protocol / abstract adapter
  cli.py         # Typer CLI (ops exit 78)
compose/         # NON-PRODUCTION TEMPLATE files only
inventories/     # draft clank registry format
docs/            # architecture notes, ADRs, runbook templates
tests/           # includes architecture guardrails
```

## Commands

```bash
# from monorepo root
make bootstrap
clank version
clank status          # exits 78
uvicorn clank_fleet.fleet_api.app:create_app --factory --host 127.0.0.1 --port 8000
curl -s http://127.0.0.1:8000/api/v1/system/ping
```

## Non-goals

No databases, Docker control, Tailscale, real auth, ingestion, or scrapers.

See `../../ARCHITECTURE_PRINCIPLES.md` and `../../DEPENDENCIES.md`.
