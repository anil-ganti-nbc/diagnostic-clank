# Phase 0 operator instance checklist

This checklist is evidence-only. The repository currently has no evidenced
live instance. `UNKNOWN` is an explicit hold state, not an invitation to infer
or probe a host. Add one copied row for every operator-confirmed instance and
attach a redacted preflight/evidence bundle.

## Current domain placeholders

| Failure domain | Instance ID | Host / failure domain | Deployed SHA / artifact | Scheduler | Database / evidence path | Backup verification | Heartbeat / freshness | Rollback artifact | Disposition |
|---|---|---|---|---|---|---|---|---|---|
| HETZNER | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` / `UNKNOWN` | `UNKNOWN` | `UNKNOWN` / `UNKNOWN` | `UNKNOWN` | HOLD |
| NAS | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` / `UNKNOWN` | `UNKNOWN` | `UNKNOWN` / `UNKNOWN` | `UNKNOWN` | HOLD |

## Required evidence for each confirmed instance

Copy the following block once per confirmed instance. Do not record hostnames,
paths, notification addresses, or command output containing credentials.

- [ ] Stable instance ID, environment, host identifier, and failure domain
      (`HETZNER` or `NAS`) are operator-confirmed.
- [ ] Deployed commit SHA, immutable artifact/image digest, source ref, and
      dependency-lock digest are recorded; repository head alone is not proof
      of deployment.
- [ ] Scheduler type, task/service identity, owner, enabled state, schedule,
      and duplicate-owner result are recorded from a redacted export.
- [ ] Database and evidence paths are recorded and their mount/permission
      checks are attached; paths are not copied from unverified documentation.
- [ ] Backup location, checksum, verification time, and isolated restore-test
      result are attached.
- [ ] Scheduler invocation, application start, successful job commit,
      heartbeat threshold, and source-freshness timestamps are attached.
- [ ] Compatible rollback artifact and its integrity/provenance evidence are
      attached.
- [ ] `promotion_eligible: false` remains until all fields are evidenced and a
      human reviewer records the decision.

## Evidence boundaries

Use `operations/phase0/preflight.py` only against an explicitly approved local
checkout and new evidence path. It is read-only and never reads file contents
or environment variables. Keep scheduler exports and logs redacted. Do not
connect to hosts, restart services, change schedulers, migrate data, rotate
credentials, or delete old definitions as part of this checklist.
