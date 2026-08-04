# Testing — clank-fleet

```bash
# from package dir
pytest -q

# architecture guardrails only
pytest -q tests/test_architecture.py

# from monorepo root
make test
make architecture
```

Architecture tests intentionally fail on:

- SQLite / SQLAlchemy / Playwright / Selenium / Scrapy / Docker SDK imports
- Existing clank repository references
- Runtime importing fleet/desktop
- Desktop importing fleet or HTTP clients
- Active port publishes in compose templates
- Docker socket mounts
- Production-looking TODOs in source
