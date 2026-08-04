# Unified Clank Infrastructure — Stage 0.5

Skeleton + architecture hardening. **No production behavior.**

```
unified-clank-stage0/
├── clank-runtime/   # shared contracts & protocols
├── clank-fleet/     # Fleet API shell, CLI, control interfaces
├── clank-desktop/   # PySide6 UI shell
├── ARCHITECTURE_PRINCIPLES.md
├── DEPENDENCIES.md
├── Makefile
└── architecture docs (v2 / v2.1-reviewed)
```

## Read first

1. `ARCHITECTURE_PRINCIPLES.md` — rules every agent must follow  
2. `DEPENDENCIES.md` — why each dependency exists  
3. `unified-clank-architecture-v2.1-reviewed.md` — authoritative amendments  
4. Package READMEs under each `clank-*` directory  

## Bootstrap

```bash
make bootstrap          # or: make install
make check              # lint + tests
make architecture       # guardrail tests only
```

Manual install order (if not using Make):

```bash
pip install -e "./clank-runtime[dev]"
pip install -e "./clank-fleet[dev]"
pip install -e "./clank-desktop[dev]"
```

## What works

| Surface | Behavior |
|---------|----------|
| `GET /api/v1/system/ping` | 200 — process shell only |
| All other Fleet API routes | 501 `STAGE0_NOT_IMPLEMENTED` |
| `clank version` | prints versions |
| Other `clank` commands | exit 78 + JSON envelope |
| Desktop app | window + placeholders, no API |
| Runtime contracts | validate / serialize models only |

## What must never appear in this stage

Databases, scrapers, outbox writers, Docker control, Tailscale setup, real auth, NAS paths, imports of existing clank repos, production logic inside placeholder modules.

Architecture tests enforce most of these. See `clank-fleet/tests/test_architecture.py`.

## Stages (do not jump ahead)

- **Stage 0** — skeleton (accepted)  
- **Stage 0.5** — this hardening pass  
- **Stage 1** — deployment foundation (Dockerize clanks, NAS, Tailscale, backups)  
- **Stage 2+** — Fleet API, runtime adapters, ingestion, desktop functionality  

## License

MIT — see `LICENSE`.
