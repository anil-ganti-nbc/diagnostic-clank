# Operations — Stage 0.5

There is **no** operational capability.

| Command | Exit | Notes |
|---------|------|-------|
| `clank version` | 0 | Prints package + API contract version |
| `clank status\|doctor\|logs\|deploy\|backup\|restore\|health\|run\|pause\|resume\|restart\|rollback` | 78 | JSON envelope `STAGE0_NOT_IMPLEMENTED` |

Compose files under `compose/` are labeled **NON-PRODUCTION TEMPLATE**. Do not deploy them to NAS.

When Stage 1 begins, operational adapters must live behind `FleetControlAdapter` and must not bind the Docker socket into the Fleet API process.
