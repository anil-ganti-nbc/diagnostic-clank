# Engineering Standard Traceability

Great Audit MUST items → ownership → Unified contract → test → stage.

| MUST | Owner | Unified contract | Test | Stage |
|------|-------|------------------|------|-------|
| Failure isolation | Clank-internal | Health/telemetry per-source status | Adapter health tests | 1+ |
| Safe state advancement | Clank-internal | N/A (not centralised); health must not claim OK on destructive failure | Conformance kit later | Clank |
| Explicit source health | Clank + Unified | `SourceHealthEntry`, `SourceHealthStatus` | `test_health_*` | 0.75 |
| Deterministic event identity | Clank-internal | `lead_id` on telemetry/ledger | telemetry roundtrip | 0.75 |
| Secret hygiene | Operator + deployment | External secrets; no secrets in contracts | architecture tests | 1 |
| Delivery accounting | Clank (+ adapter) | `DeliveryStatus`; capability flag | enum + adapter caps | 1–2 |
| Prod/experimental separation | Clank + Fleet display | `SourceLifecycleState`, `ReleaseChannel` | lifecycle transitions | 0.75 |
| Incident regression | Clank-internal | Conformance kit scenarios | kit (later) | 2 |
| Timezone honesty | Clank-internal | UTC datetimes in contracts | model validation | 0.75 |
| Single-instance/overlap | Clank-internal | `SKIPPED_OVERLAP` status value | health enum | 0.75 |

## Cross-cutting

| Concern | Layers |
|---------|--------|
| Health envelope | Clank interprets → adapter exports → Fleet/Desktop display |
| Telemetry IDs | Clank emits → Fleet stores → Ledger joins → ClankOps later |
| Fallback fencing | Desktop + Fleet ownership service + Clank Level 3 support |
| Backups | Deployment (NAS) + operator restore drills |
