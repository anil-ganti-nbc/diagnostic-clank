# Portability Checklist

Use once per clank. Check items with evidence (command output or file path).

## Preflight
- [ ] Repository builds/tests on Linux without Windows-only imports
- [ ] Entry points documented (`console_scripts` or `python -m`)
- [ ] One-shot command exists (or can be exposed without new scheduler)
- [ ] Existing tests pass **before** portability changes
- [ ] Secrets not committed; env/file pattern known

## Paths & state
- [ ] No hard-coded `C:\` or Windows drive letters in runtime code
- [ ] DB / evidence / cache paths configurable or cwd-relative
- [ ] Single authoritative path resolution (env override optional)
- [ ] Persistence directory identified for volume mount

## Process
- [ ] No browser auto-open by default in container (`*_OPEN_BROWSER=0`)
- [ ] Logging to stdout/stderr acceptable for containers
- [ ] SIGTERM leaves no orphan workers (document if long-lived server)
- [ ] Scheduler remains **external** (cron/compose/NAS task)

## Contracts
- [ ] `version` command
- [ ] `identity` payload (Stage 0.5 RuntimeIdentity fields)
- [ ] `health` payload without claiming false productivity
- [ ] Health uses null/unknown when history absent
- [ ] Inventory draft entry added

## Docker
- [ ] `docker build` succeeds on linux/amd64
- [ ] `docker compose config` validates
- [ ] `version` / `identity` / `health` run **inside** container
- [ ] Safe one-shot run (dry-run/fixture) exit code verified
- [ ] Persistence: write → remove container → recreate → state present
- [ ] Non-root user
- [ ] No public ports unless explicitly documented
- [ ] No Docker socket mount

## Safety
- [ ] Production DB not mutated by validation tests
- [ ] Rollback: previous launcher/scripts still work on Windows if needed
- [ ] Architecture deviations listed or "none"
