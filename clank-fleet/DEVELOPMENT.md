# Development — clank-fleet

From the monorepo root:

```bash
make bootstrap
make check
make architecture
```

Local API shell:

```bash
uvicorn clank_fleet.fleet_api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Only `/api/v1/system/ping` is expected to return 200.

Coding standards and ownership: see `../ARCHITECTURE_PRINCIPLES.md` and `../CONTRIBUTING.md`.
