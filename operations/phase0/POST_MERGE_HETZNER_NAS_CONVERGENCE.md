# Post-merge Hetzner/NAS convergence checklist

This is a controlled rollout checklist, not an authorization to merge or
deploy. Keep promotion frozen until the operator has completed the evidence
package and a human reviewer approves each failure-domain wave separately.

## Before either wave

- [ ] The final PR/SHA table in `PR_HEADS.md` matches the reviewed draft heads.
- [ ] The canonical ledger has one reviewed row per discovered instance;
      domain placeholders remain `UNKNOWN` until then.
- [ ] For the target instance, attach read-only preflight output, redacted
      scheduler/service export, dependency-lock digest, SBOM/provenance,
      current SHA/artifact digest, and a compatible rollback artifact.
- [ ] Back up database, configuration, evidence, and scheduler state outside
      the release directory; record checksums and an isolated restore test.
- [ ] Identify one scheduler owner and one notification owner. Do not delete
      duplicate definitions; quarantine them under the approved change plan.
- [ ] Confirm loopback dashboard binding, unauthenticated mutation rejection,
      mount/permission checks, clock/network checks, and redacted logs.

## Hetzner wave

- [ ] Record the exact instance ID, host/failure domain, SHA/artifact, scheduler,
      database/evidence paths, backup verification, heartbeat/freshness, and
      rollback artifact in the ledger.
- [ ] Quiesce only during the approved window; verify no job is in flight.
- [ ] Rehearse migration against the isolated restore and record schema
      revisions before touching the candidate release.
- [ ] Install the immutable approved artifact in a new release directory and
      run exactly one migration/start owner.
- [ ] Capture post-update evidence, including two unattended runs, successful
      commits, success-heartbeat advancement after completion, source freshness,
      notification de-duplication, and restart integrity.
- [ ] Stop and roll back on artifact mismatch, migration error, wrong mount,
      exposed dashboard, duplicate owner, stale heartbeat, credential-bearing
      log, or restart failure.
- [ ] Hold the NAS wave until a reviewer signs the Hetzner evidence bundle.

## NAS wave

- [ ] Repeat the same preflight, backup/restore, scheduler-ownership, artifact,
      migration, two-run, freshness, notification, and rollback checks against
      the NAS instance; do not reuse Hetzner evidence.
- [ ] Verify NAS ownership/fencing and that no stale Hetzner process can become
      a second writer. Failback is explicit; no automatic dual-primary.
- [ ] Hold promotion if NAS mount, backup, rollback, or heartbeat evidence is
      `UNKNOWN`; update the ledger only after reviewer acceptance.

## Completion record

- [ ] Attach the redacted evidence bundle and post-update record for each wave.
- [ ] Record operator, reviewer, UTC timestamps, final SHA/artifact, and
      rollback compatibility in `fleet.yaml` and the instance evidence record.
- [ ] Set `promotion_eligible: true` only through a separate human-approved
      governance change after both waves pass. No script in this package changes
      that field or mutates a host.

