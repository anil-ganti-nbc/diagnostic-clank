# unified-clank-architecture-v2.1-reviewed.md

> **Status:** Architecture Reviewed & Conditionally Approved  
> **Reviewer:** ChatGPT  
> **Base Document:** Gemini `unified-clank-architecture-v2.md`

---

# Review Summary

The Gemini proposal is accepted as the architectural baseline with targeted amendments.

Overall score: **9.2 / 10**

The following amendments supersede the original document where they conflict.

---

## Architecture Amendment 1 — Split Version 1 from Version 2 (P0)

**Reason**

The original proposal mixes survival work needed before **14 August** with long-term platform work.

**Approved P0**

- Dockerized clanks
- NAS deployment
- Tailscale
- Persistent domain databases
- Backup + restore verification
- Fleet control contract
- Minimal Fleet CLI
- Health contract

**Deferred (P1/P2)**

- Central ingestion
- Desktop client
- Fleet API
- Unified newsroom database
- Historical imports
- Story clustering

---

## Architecture Amendment 2 — Introduce Clank Runtime

Create a shared `clank-runtime` package containing only infrastructure concerns.

Owns:

- logging
- configuration
- health contract
- metadata
- retry helpers
- heartbeat
- graceful shutdown
- event contract helpers

Does **not** own:

- scraping
- collectors
- schedulers
- domain models
- business logic

---

## Architecture Amendment 3 — Version Every External Contract

Every clank must expose:

```json
{
  "contract_version":1,
  "runtime_version":"1.0",
  "clank_version":"0.1.0"
}
```

Health, Fleet API and Event contracts must evolve independently.

---

## Architecture Amendment 4 — Replace Shared JSONL With Producer Spools

The proposed shared append-only JSONL files are replaced.

Each producer owns:

```
/shared/outbox/
    oem-radar/
    smartphone/
    watch/
    chinese/
```

Rules:

- one writer per spool
- immutable event files
- atomic rename
- checkpoint ledger
- replay support
- quarantine directory
- bounded storage
- disk usage alarms

---

## Architecture Amendment 5 — Event Adapters are NOT P0

Operational migration precedes data-platform migration.

Order:

1. Deploy clanks safely
2. Preserve databases
3. Verify backups
4. Complete soak testing
5. Introduce export adapters
6. Build ingestion

---

## Architecture Amendment 6 — Fleet CLI

Required utility:

```
clank status
clank doctor
clank logs
clank deploy
clank backup
clank restore
clank health
```

Desktop GUI consumes Fleet API.

CLI remains universal recovery interface.

---

## Architecture Amendment 7 — Release Channels

Every clank has:

- Experimental
- Soaking
- Staging
- Production
- Repair
- Deprecated

Operational state is separate from release maturity.

---

## Architecture Amendment 8 — Architecture Tests

Mandatory tests:

- Linux compatible
- Docker build
- No Windows-only imports
- No writes outside persistent paths
- Health endpoint present
- Runtime contract valid
- Event contract valid
- Backup hook present
- Restore test passes

---

## Architecture Amendment 9 — Central Store Decision Deferred

SQLite remains the preferred candidate but is **not frozen** until workload measurements exist.

Upgrade criteria must be documented.

---

## Architecture Amendment 10 — Expanded Central Model

Add placeholders for:

- Sources
- Evidence
- Artifacts
- JobRuns
- CollectorRuns
- IngestionBatch
- IngestionError
- EditorialAudit
- DeploymentHistory

These are projections only.

---

## Architecture Amendment 11 — Stronger Confidence Model

Replace single numeric confidence with dimensions:

- source reliability
- evidence strength
- corroboration
- freshness
- parser quality
- ingestion quality
- entity certainty

Never collapse into one score.

---

## Architecture Amendment 12 — Native Desktop Priority

Native PySide6 desktop remains approved.

However:

Desktop implementation is **P1**.

Backend contracts are **P0**.

---

## Architecture Amendment 13 — Governance

The governance addendum supplied separately is authoritative.

Workflow:

Gemini
→ Architecture

ChatGPT
→ Review & approval

Codex / Claude
→ Implementation

Grok
→ Adversarial review

ChatGPT
→ Release decision

---

# Final Approved Priorities

## Before August 14

- Feature freeze
- Dockerize
- NAS deployment
- Backup validation
- Runtime contract
- Fleet CLI
- Health contract
- Tailscale

## Immediately After

- Runtime library
- Fleet API
- Desktop client
- Event adapters
- Unified store

## Later

- Historical imports
- Story clustering
- Cross-clank intelligence
- Search improvements
- Release automation

---

# Approval

The reviewed architecture is approved as the implementation baseline **provided these amendments override conflicting sections of the Gemini draft**.
