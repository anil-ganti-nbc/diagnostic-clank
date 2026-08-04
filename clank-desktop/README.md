# clank-desktop

Native PySide6 desktop **shell** for Unified Clank.

**Stage 0.5 — UI skeleton only. Not connected to Fleet API.**

## Allowed

- One native window, Stage 0 label
- Placeholder navigation views (“Not implemented in Stage 0”)
- Disabled operational actions
- About dialog and version

## Forbidden

API calls, HTTP clients, local DBs, NAS/Docker access, auth, tray sync, fake data grids, auto-update.

## Launch

```bash
pip install -e ".[dev]"
clank-desktop
# headless / CI:
QT_QPA_PLATFORM=offscreen CLANK_DESKTOP_TEST_SAFE=1 clank-desktop
```

Desktop is P1/P2 per reviewed architecture. This package only reserves the boundary.
