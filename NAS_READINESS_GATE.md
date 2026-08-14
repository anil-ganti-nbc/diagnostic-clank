# NAS Readiness Gate

A Clank is NAS-ready only when:

- [ ] Canonical / conformance tests pass
- [ ] Known P0 silent-miss / corruption issues = zero (or accepted with written waiver)
- [ ] P1 silent-miss blockers resolved or explicitly accepted
- [ ] Successful Linux (or target NAS OS) run
- [ ] Local persistent DB volume tested
- [ ] Backup + restore drill passed
- [ ] Health export available (adapter or CLI)
- [ ] Basic telemetry available (even JSONL)
- [ ] Secrets externalised
- [ ] Baseline events do not flood alerts
- [ ] Source failure isolation proven
- [ ] Scheduler / restart policy verified
- [ ] No production secrets in image or git

Machine-readable mirror may later live under `inventories/`.
