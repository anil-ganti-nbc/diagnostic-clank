# Board observer admission contract

COPS-000074 ports Board observation onto adapter-package base
`fbf286b45594280506c7c00ad54162259a82e0c8`. Board schema semantics are audited
against child source `613c3a13c0e52088eeb33d6266b6ca7b2b783000`. This document
does not authorize production inventory admission, collection, promotion,
delivery or scheduler changes.

The required observer surface remains **0.2**: `identity`, `capabilities`,
`status`, `health`, `last_run`, `capability_states`. Shared descriptor/payload
version `0.1.0-v3` is a separate namespace. Board remains experimental.

`BoardClankAdapter(db_path=...)` reads only a governed, sealed schema-v3
SQLite snapshot. It rejects missing/unreadable state, incompatible schemas,
incomplete native tables/observer columns, failed foreign keys, WAL headers
and SQLite sidecars. Connections use read-only immutable URIs and query-only
mode. Snapshot contract 1.0 additionally supplies verified provenance,
integrity/hash/bytes, intake freshness, native-clock freshness and package/
artifact pins; those checks are not replaced by the adapter.

`clank_id` is `board-clank`. Instance and lane are not guessed from its DB
filename or the child source's historic local-workstation default. Motherclank
explicit `--adapter-registry` rows bind `instance_id`, `lane_id` and expected
schema `3` to the snapshot manifest. Registry store/identity validation remains
mandatory. Diagnostic's native factory supports explicit `board_db=` opt-in;
its existing five default registrations are unchanged. Registration enables
observation only, never a child source. Board QC remains unqualified.

## Native summaries

`source_summary()` preserves the child-native roster ordered by source_key:
`source_key`, `vendor`, `plane`, `authority`, `enabled`, `promotion_state`,
`registered_state`. It is policy evidence, not source-health or novelty proof.
An absent source table returns `[]`; availability is explicitly qualified in
`observer_evidence`. An unrelated missing table does not erase readable roster
evidence, but core compatibility/health remains UNKNOWN.

`diagnostic_summary()` preserves native `conditions` grouped by
source_key/diagnostic_type/status/reason with count `n`, ordered by
source_key/diagnostic_type/status, and `sightings_total`. Missing conditions
returns `conditions: []`, `sightings_total: "UNKNOWN"`. Missing sightings
preserves readable conditions with an UNKNOWN total. These are durable
uncertainty records, never new market events, alerts or condition-closure
authority. Unsupported schemas fail closed for both summaries.

## Optional observer evidence 1.0

`observer_evidence()` is an additive optional extension with
`payload_version: "1.0"`. It contains explicit native-summary/core availability,
schema evidence, per-source policy/latest attempt/latest accepted native run/
receipt/baseline/recent errors, diagnostic condition identities and transitions,
sightings and their emitted-event references, event counts by baseline silence,
revision evidence, observation age policy and explicit absence of mutation
authority. Null run/receipt/baseline means no such row was observed, not success.

Condition and sighting detail arrays are bounded at 1,000 with total counts
and truncation markers. Sightings expose the most recent 1,000 in chronological
ID order. Transition-event evidence is limited to the most recent 1,000 and
preserves native event keys/types/payloads. Native summaries remain untruncated.
Source error history and global recent runs are limited to 20. An unchanged
condition's repeated sighting is preserved without manufacturing novelty.
Reappearance remains native status OPEN with its recorded transition evidence.

Historical `events.code_revision` identifies the event producer only.
`code_revision()` is explicitly that historical value. Child source and
deployed revision are UNKNOWN in database-only evidence; independent manifest
host evidence carries their values separately. Adapter source SHA and image
digest remain separate pins. A stamped schema, recent accepted run or image
existence alone cannot establish currently healthy runtime or source coverage.

The adapter's default native execution age horizon is **24 hours**, an
explicit isolated-observation policy, not a claim of scheduled collection.
The governed manifest retains its independently declared freshness horizon.
Missing, invalid, future or stale native clocks cannot become current health.
Disabled policy alone is not source failure. A recent recorded latest failure
is visible; an older failure superseded by acceptance does not permanently
mark a source failed. Accepted runs, resolved diagnostics, and intact schema
do not establish complete source coverage, so UNKNOWN is retained.

Native source/deployed/backup/restore semantics are distinct. Survivability
is unknown/unverified from a DB alone because current NAS backup/restore proof
is external. Scheduler, sender, source enablement, promotion and diagnostic
closure are unsupported by observer policy.

Motherclank consumes the two summaries only through its versioned optional
extension dispatch after recognizing observer evidence 1.0. It preserves these
structures verbatim, including during stale/UNKNOWN synthesis, and performs
no Board-specific SQL or reinterpretation. Missing/failed evidence remains
visible and must not poison sibling observations or become a healthy zero.
