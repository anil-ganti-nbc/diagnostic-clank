# Canonical fleet inventory

`inventories/fleet.yaml` is the Phase 0 control-plane ledger for the 13 reviewed
repositories. It records repository truth separately from deployment truth.

An exact `source_sha` means only that the repository head was inspected. It is
not evidence that the commit is deployed. Until a maintainer verifies a host,
artifact, scheduler, database, credentials owner, notification authority,
backup, and rollback target, those fields remain `UNKNOWN` and the system is
labelled `UNVERIFIED_PRODUCTION` or `PROTOTYPE`.

Do not delete unknown systems to make fleet health appear green. Resolve each
`UNKNOWN` from host evidence, or record that the deployment was quarantined or
disabled. Promotion remains frozen while any entry has
`promotion_eligible: false`.

`deployment_facts` in the ledger contains one explicit placeholder for each
supported failure domain (`HETZNER` and `NAS`). Those placeholders intentionally
keep every host, artifact, scheduler, database/evidence, backup, freshness, and
rollback field at the literal value `UNKNOWN`; they are not live-instance rows.
`deployments` remains empty until an operator has evidence for a specific
instance. Replace a placeholder only from a reviewed, redacted evidence bundle.

This file contains no credentials, webhook URLs, or secret values. Owners and
locations must be recorded as stable identifiers, not secrets.
