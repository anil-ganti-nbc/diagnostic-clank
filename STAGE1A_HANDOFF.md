# Stage 1A Handoff

## Branches

- Base v3: `unification-v3-2026-08` @ Architecture v3 commit
- Stage 1A: `unified-stage1a-2026-08`

## Bootstrap

```bash
pip install -e "./clank-runtime[dev]"
pip install -e "./clank-fleet[dev]"
pip install -e "./clank-desktop[dev]"
cd clank-runtime && python -m pytest -q
cd ../clank-fleet && python -m pytest -q
```

## Demo (fixture DBs)

```bash
export OEM_RADAR_DB=clank-fleet/tests/fixtures/oem_radar_fixture.db
export FEATURE_PHONE_CLANK_DB=clank-fleet/tests/fixtures/feature_phone_fixture.db
python -c "from clank_fleet.adapters.factory import build_default_registry; import json; print(json.dumps(build_default_registry().fleet_summary(), indent=2, default=str))"
```

## External revisions used

- oem-radar: `3a4d0a1` (public main shallow clone)
- feature-phone-clank: `f7eda73` (public main shallow clone)

## Push

GitHub credentials unavailable in build environment — use bundle/patch under artifacts.
