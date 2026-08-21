# Phase 0 Hetzner/NAS convergence package

This package prepares operator evidence. It does not connect to a remote host,
change a scheduler, update a checkout, run a migration, or delete data. The
repository promotion freeze remains in force.

## 1. Preflight (read-only)

Copy this repository to the explicitly approved target or run it from an
approved local checkout on that target. Use an absolute repository path and a
new evidence path:

```text
python operations/phase0/preflight.py \
  --target-type HETZNER \
  --instance-id semint-hetzner-stage-01 \
  --repository-path /absolute/path/to/repository \
  --evidence-out /absolute/restricted/path/preflight.json \
  --inspect-path database=/absolute/path/to/database.db \
  --inspect-path evidence=/absolute/path/to/evidence
```

`--target-type NAS` is required for NAS instances. Ambiguous target types,
relative paths, broad filesystem roots, existing evidence files, and
secret-like labels are rejected. File content and environment variables are
never read. Review the JSON before attaching it to the canonical ledger.

## 2. Backup and rollback checkpoint

- Export scheduler/service definitions without embedded credential values.
- Quiesce only under an approved change window; the scripts here do not do it.
- Back up database, configuration, evidence, and scheduler state outside the
  mutable release directory.
- Record checksums and restore the backup into a separate path. Listing a
  backup is not a restore test.
- Record the current SHA/artifact/image digest and the exact compatible
  rollback artifact.
- Refuse an update if any database, mount, scheduler owner, notification owner,
  backup, or rollback fact is `UNKNOWN`.

## 3. Approved update procedure

1. Attach a reviewed preflight record to the instance ledger row.
2. Verify the candidate immutable SHA/digest, signature, provenance, and SBOM.
3. Disable duplicate schedulers/processes without deleting their definitions.
4. Quiesce the one approved instance and verify no job is in flight.
5. Rehearse migrations against the isolated restore; record schema revisions.
6. Install the exact approved artifact in a new release directory. Do not pull
   a moving branch or mutable image tag.
7. Run the migration once, start one service owner, and perform the checks in
   `post-update-evidence.template.md`.
8. Update Hetzner and NAS as separate waves. Complete two unattended runs and
   review one wave before authorizing the other.

No mutation helper is supplied in Phase 0: deployment mechanisms differ by
host and remain `UNKNOWN`. An implementation must later require an explicit
`--execute`, exact `--instance-id`, exact approved digest, completed preflight
record, and interactive confirmation; it must still never delete data.

## 4. Rollback

Stop on artifact mismatch, migration/integrity error, wrong mount, external
dashboard exposure, duplicate scheduler/notifier, missing success heartbeat,
credential-bearing log, or restart failure. Disable the candidate, preserve
redacted evidence, restore the coherent pre-update database/config/evidence set
when backward compatibility is not proven, restore the exported scheduler, and
start the pinned prior artifact. Re-run integrity, containment, freshness,
notification-deduplication, restart, and one unattended-run checks. Do not
continue into the other failure domain.
