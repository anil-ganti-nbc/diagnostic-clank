# Dependency Audit — Stage 0.5

Every runtime dependency must justify its presence. Prefer the standard library.

## clank-runtime

| Dependency | Why | Could stdlib replace it? |
|------------|-----|--------------------------|
| `pydantic>=2.7,<3` | Contract models, validation, serialization | Partially (dataclasses), but loses validation and JSON schema quality required for cross-agent contracts |
| `typing-extensions>=4.12` | `runtime_checkable` / Protocol backports if needed on edge Python builds | On pure 3.11+ most Protocol features are in stdlib; kept for conservative compatibility. Candidate for removal in a later hardening pass if CI is locked to 3.11+. |

**Dev only:** pytest, pytest-cov, ruff, pyright.

## clank-fleet

| Dependency | Why | Could stdlib replace it? |
|------------|-----|--------------------------|
| `fastapi` | API shell, OpenAPI metadata, typed routes | No — stdlib http.server is not a typed API contract surface |
| `uvicorn[standard]` | ASGI server to *launch* the shell for local checks | Could use another ASGI server; uvicorn is the conventional FastAPI pair |
| `pydantic` | Request/response models shared with runtime patterns | Same as runtime |
| `pydantic-settings` | Configuration convention placeholder | Could use os.environ only; kept as a thin convention layer. Revisit if unused in Stage 1. |
| `typer` | CLI parsing and help | argparse is possible but Typer gives consistent help and exit handling with less code |
| `clank-runtime` | Shared contracts | Required |

**Dev only:** pytest, httpx (TestClient companion), pyyaml (compose/inventory parse tests), ruff, pyright.

## clank-desktop

| Dependency | Why | Could stdlib replace it? |
|------------|-----|--------------------------|
| `PySide6` | Native desktop shell (approved architecture) | No — tkinter is not the approved UI stack |

**Dev only:** pytest, pytest-qt (optional), ruff, pyright.

## Explicitly rejected (must not appear in Stage 0 / 0.5 source)

- sqlite3 / SQLAlchemy / any ORM
- Playwright / Selenium / Scrapy / browser automation
- Docker SDK with socket mounts
- Production HTTP client usage inside runtime source (httpx only in tests)
- Kafka, Redis, PostgreSQL drivers

## Install order

```bash
pip install -e "./clank-runtime[dev]"
pip install -e "./clank-fleet[dev]"
pip install -e "./clank-desktop[dev]"
# or: make bootstrap
```
