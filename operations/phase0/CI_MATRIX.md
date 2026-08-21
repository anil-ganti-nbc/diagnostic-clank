# Phase 0 CI matrix

All active workflows live at repository root in `.github/workflows/phase0-ci.yml` and,
for repositories with a Dockerfile, `.github/workflows/phase0-container.yml`.
Action references are pinned to commits, permissions are read-only, live
provider access is denied through hermetic test proxy settings, and
required commands contain no silent-success fallback.

| Repository | Required implemented jobs | Windows | Container | Stateful gate | Remaining/advisory gap |
|---|---|---:|---:|---|---|
| diagnostic-clank | install/lint/types, collection/tests, secrets/dependencies, package/SBOM/provenance | Required | Required | Existing backup/restore test | Full formatting is advisory; known pre-existing failures remain visible. |
| clank-architecture | conformance/links, secrets, docs archive/provenance | N/A | N/A | N/A | External-link reachability remains advisory. |
| semiconductor-intelligence | install/lint, collection/tests, secrets/dependencies, package/SBOM/provenance | Required | Required | Existing backup-health test | Real Task Scheduler gate remains operator-only; deprecation warnings remain visible. |
| chinese-tech-wire | hash install/lint, collection/tests, secrets/dependencies, source/SBOM/provenance | Required | Required | Scheduler/security persistence tests | Full backup/restore test and credential audit remain open. |
| watch-clank | locked install/lint, collection/tests, secrets/dependencies, package/SBOM/provenance | Required | Required | DB/migration tests | Dedicated backup/restore round trip remains open. |
| smartwatch-clank | locked install/lint, collection/tests, secrets/dependencies, package/SBOM/provenance | Required | Required | Not yet implemented | Backup/restore required before a stateful deployment can be verified. |
| feature-phone-clank | locked install/lint, collection/tests, secrets/dependencies, package/SBOM/provenance | Required | Required | Migration test | Dedicated evidence backup/restore remains open. |
| smartphone-clank | hash install/lint, collection/tests, secrets/dependencies, source/SBOM/provenance | Required | Required | Runtime-path/state tests | Dedicated backup/restore round trip remains open. |
| tablet-clank | locked install/lint, collection/tests, secrets/dependencies, package/SBOM/provenance | Not evidenced | N/A | Not yet implemented | Host support and backup mechanism remain `UNKNOWN`. |
| korean-tech-wire | locked install/lint, collection/tests, secrets/dependencies, package/SBOM/provenance | Required | N/A | Storage tests | Dedicated backup/restore round trip remains open. |
| free-game-tracker | locked install/lint/types, collection/tests, secrets/dependencies, package/SBOM/provenance | Required | Required | Database/migration tests | Backup script round-trip needs a dedicated hermetic test. |
| oem-radar | locked install/lint, collection/tests, secrets/dependencies, package/SBOM/provenance | Required | Required | Feedback persistence test | Backup/restore and outbox recovery tests remain open. |
| unified-clank-platform | install/lint/types, collection/tests, secrets/dependencies, package/SBOM/provenance | Frozen/N/A | Frozen/N/A | N/A | Supersession review is required; no release workflow is permitted. |

## Proposed required branch-protection checks

Require every job present in a repository’s workflow:

- `ci / install-lint-types`
- `ci / tests-and-collection`
- `security / secrets-and-dependencies` (or `security / secrets` for governance)
- `build / package-sbom-provenance` (or `build / governance-provenance`)
- `build / container-smoke` where a Dockerfile is deployable
- `state / backup-restore` where currently implemented
- `platform / windows` where Windows is declared/supported
- `policy / phase0-conformance` for governance and, once wired to the ledger,
  every promotable repository

`advisory / full-style-format` is intentionally non-blocking while legacy
format debt is baselined. It has no `|| true`; GitHub records the real result.
Live source/provider probes, long soak, native macOS packaging, performance,
and scheduled all-history/image-registry scans are advisory but any confirmed
credential finding is an incident and blocks promotion.

No branch-protection setting is changed by this repository patch. An operator
must enable these names only after workflows appear on the default branch and
must not waive failures to close Phase 0.
