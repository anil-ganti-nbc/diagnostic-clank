

As an AI, I don't have a direct file attachment feature, but I have formatted the complete architectural overview into a clean, raw Markdown block below.

You can easily use the "Copy code" button in the top right corner of the block and paste it into your text editor of choice, then save it as unified-clank-architecture-v2.md.
Markdown

# unified-clank-architecture-v2.md

## 1. Executive Summary

The Unified Clank Infrastructure V2 transitions an isolated collection of newsroom scrapers into a resilient, cross-domain intelligence platform. Driven by the hard deadline of August 14, 2026, when the Windows desktop becomes unavailable, the architecture separates survival from expansion. It utilizes a decentralized **JSONL Outbox** pattern for ingestion to guarantee zero data loss, retains domain data authority within individual Clank SQLite databases, and builds a **Central Intelligence Store** for editorial review. A **Native PySide6 Desktop Client** serves as the primary newsroom interface, communicating securely over Tailscale via a central **Fleet API**.

## 2. V1 vs V2 Scope

| Scope Phase | Timeline | Focus | Key Deliverables |
| :--- | :--- | :--- | :--- |
| **P0: Survival** | Pre-Aug 14 | Operational continuity | Dockerized clanks, NAS deployment, Tailscale, Domain SQLite persistence, JSONL Outbox adapters, HyperBackup verification. |
| **P1: Usability** | Post-Aug 14 | Ingestion & Core API | Central Ingestion Worker, Central SQLite Store, FTS5 Search, FastAPI Fleet API. |
| **P2: Expansion** | Future | Newsroom operations | Native PySide6 Desktop App, Historical Data Imports, Cross-clank entity resolution, Restic/B2 offsite backups. |
| **Rejected** | N/A | Avoiding bloat | Kubernetes, PostgreSQL, Kafka/RabbitMQ, Semantic/Embedding Search, Electron Desktop App, UI Dashboards. |

## 3. Final Architecture

### Major Component Inventory

| Component | Purpose | Owner | Dependency | Failure Impact | Resource Cost | Rollout |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Docker Engine** | Host clank containers | Infrastructure | Synology NAS | Complete fleet outage | 1.5 GB RAM | **P0** |
| **Domain Databases** | Authoritative clank data | Clanks | File system | Loss of single domain history | Minimal I/O | **P0** |
| **Outbox Adapters** | Write events to JSONL | Clank Runtime | Shared NAS volume | Single clank data stalls | Negligible | **P0** |
| **Tailscale** | Secure remote access | Infrastructure | Internet | Loss of remote admin/API | <50 MB RAM | **P0** |
| **Ingestion Worker** | Process JSONL outboxes | Shared Platform | Outbox volumes | Data remains in outbox | <100 MB RAM | **P1** |
| **Central Store** | Normalized intelligence DB | Shared Platform | Ingestion Worker | API/Search degrades | ~100 MB RAM | **P1** |
| **Fleet API** | Central REST interface | Shared Platform | Central Store | Desktop app fails to sync | ~150 MB RAM | **P1** |
| **PySide6 Client** | Native Desktop GUI | Newsroom | Fleet API | Fallback to CLI/API | Client-side | **P2** |

## 4. Architecture and Data-Flow Diagrams

### System Architecture
```text
[ MacBook (ARM64) ]                 [ GitHub Actions (AMD64 Builds) ]
       | (Dev/Control)                              |
       v                                            v
[ Tailscale Mesh ] ---------------------> [ Synology DS923+ ]
       ^                                            |
       |                               +-------------------------+
[ Windows Desktop ]                    |  +-------------------+  |
[ (PySide6 Client)  ]                  |  | Clanks (Isolated) |  |
       ^                               |  |  (Domain SQLite)  |  |
       | (REST / JSON)                 |  +--------+----------+  |
       v                               |           | (Writes JSONL)
[ Fleet API (FastAPI) ] <----------+   |           v             |
[ Central DB (SQLite) ] <----------|---|--[ Shared Outbox Vol ]  |
[ FTS5 Search Index   ]            |   |  | Ingestion Worker  |  |
                                   +---|--| (Reads JSONL)     |  |
                                       |  +-------------------+  |
                                       |            |            |
                                       +------------|------------+
                                                    v
                                         [ HyperBackup / Restic ]

Live Ingestion Data-Flow
Plaintext

(1) Clank Scraper -> (2) Domain SQLite -> (3) Outbox Adapter -> (4) /shared/outbox/clank.jsonl
                                                                       |
(7) Central SQLite <- (6) Validate & Deduplicate <- (5) Ingestion Worker Polls (10s)

5. Data Ownership Model

    Layer A (Authoritative Domain): Clanks own domain models. OEM Radar owns laptop_skus, Watch Clank owns casio_references. The central platform has zero knowledge of these raw schemas.

    Layer B (Unified Newsroom): The Central Store owns the normalized projections (Events, Entities), relationship hints (StoryClusters), and newsroom workflow (EditorialState).

    Immutability Rule: Historical imports and ingestion workers never write back to Layer A domain databases.

6. Event Envelope and Ingestion Design

JSONL Outbox Pattern (P0): Instead of fragile HTTP pushes, clanks append line-delimited JSON to a shared Docker volume. The Ingestion Worker polls, processes within a BEGIN EXCLUSIVE transaction, and moves the file to /archive.

Event Envelope Specification:
JSON

{
  "contract_version": 1,
  "event_id": "uuid4",
  "producer": "oem-radar",
  "schema_name": "product_change",
  "schema_version": 1,
  "occurred_at": "2026-08-01T08:00:00Z", 
  "supersedes_event_id": null, 
  "source_url": "[https://oem.com/laptop](https://oem.com/laptop)",
  "entities": [
    {"type": "product", "id": "sku-123", "name": "ThinkPad X1"}
  ],
  "confidence": {
    "source_reliability": 9,
    "evidence_strength": 10
  },
  "payload": {
    "old_price": 999, "new_price": 799, "reason": "discount"
  },
  "payload_hash": "sha256-hash"
}

7. Central Data Model

SQLite schema for the Central Intelligence Store (P1):
Table	Primary Key	Critical Columns	Notes
Producers	id	name, last_heartbeat	Fleet health tracking.
Events	id	producer_id, occurred_at, payload	The core unified ledger. JSON stored in payload.
Entities	id	canonical_name, type	Global cross-clank identities.
EntityAliases	producer_id	domain_entity_id, entity_id	Maps clank identities to global entities.
StoryClusters	id	topic_name	Soft groupings of Events.
ClusterLinks	event_id	cluster_id, confidence	Relational join table.
EditorialState	event_id	status, notes, is_bookmarked	Mutated by newsroom UI.
Events_FTS	rowid	payload, source_url, entities	Virtual table for SQLite FTS5.
8. Per-Clank Adapter Plan

    OEM Radar: Emits product_new, product_delisted, price_change. (P0)

    Free Game Tracker: Emits promotion_started, promotion_expiring. (P0)

    Watch Clank: Emits variant_released, reference_updated. (P0)

    Smartphone Clank: Emits certification_found, firmware_spotted. (P0)

    Chinese Tech Wire: Emits article_published. Translates titles/summaries into the payload for FTS5 indexing. (P0)

    Semi Intel: Emits rumor_observed. Strict requirement: Must dynamically set confidence.source_reliability based on account history to avoid polluting the central queue. (P1 Repair)

9. Historical Data Migration

Export Script Pattern (P2):
To avoid polluting live scraping logic, historical imports use isolated scripts (export_history.py) run inside the clank containers.

    Mount the legacy SQLite database as read-only.

    Query legacy records.

    Transform into standard Event Envelopes.

    Write to /shared/outbox/historical/<clank>.jsonl.

    The Ingestion Worker processes them normally, preserving exact occurred_at timestamps.

10. Entity Resolution and Deduplication

    Hard Deduplication (P1): Ingestion Worker drops records with identical payload_hash from the same producer within a 24-hour window.

    Soft Clustering (P2): Overlapping signals (e.g., Semi Intel and Tech Wire reporting the same rumor) generate separate Events. UI/Heuristics map them to a StoryCluster.

    Entity Mapping (P2): Domain aliases ("S26 Ultra" vs "Galaxy S26") map to a single Canonical ID in Entities via EntityAliases, ensuring original evidence text is never altered.

11. Search and Retention

Search Architecture (P1): SQLite FTS5 indexing payload JSON values, translated titles, and entities. Deterministic text search only for V1/V2. Embeddings are rejected due to recurring API costs.

Data Tiering & Retention:
Data Type	Location	Retention Rule
Event Envelopes	Central SQLite	Indefinite (High value, low footprint).
Editorial Notes	Central SQLite	Indefinite.
HTML / Source Text	NAS File System	Purge after 90 days (Unless bookmarked).
Images / Screenshots	NAS File System	Purge after 180 days (Unless bookmarked).
12. Fleet API

Framework: FastAPI (Python). (P1)
Authentication: Static Bearer Token via environment variables. Tailscale ensures network layer security.
Contract: Exposes Newsroom Intelligence operations and restricted Fleet Control execution (via shell wrappers, not direct Docker socket binding).
Plaintext

GET /api/v1/queue
POST /api/v1/events/{id}/review
GET /api/v1/fleet/status
POST /api/v1/clanks/{id}/action (e.g., restart, backup)

13. Native Desktop App

Framework: Python with PySide6 (Qt). (P2)
Rationale: Native OS performance, cross-platform compilation (Windows .exe, Mac ARM64 app), avoids Electron RAM bloat, prevents browser-tab fatigue.
Design:

    Offline-capable: Maintains a local SQLite cache of the last 1,000 queue items.

    Interacts only with the Fleet API, never directly with NAS files or Docker.

    Pages: Unified Queue, Fleet Health, Clank Dossiers (e.g., specific OEM views).

14. Deployment and GitHub Workflow

    Repositories: One per Clank (e.g., watch-clank), one clank-fleet (Infrastructure/API), one clank-desktop.

    Workflow:

        P0: git pull -> docker compose up -d on NAS via Tailscale SSH.

        P1/P2: GitHub Actions builds linux/amd64 images -> pushes to GHCR -> NAS pulls via read-only token.

    Branching: Single writing agent per branch rule strictly enforced. main tracks production.

15. Security, Backups, and Power Resilience

    Security: Tailscale mesh only. Zero public router ports. API token stored in Windows Credential Manager.

    Power Resilience: Synology UPS integration. SQLite PRAGMA journal_mode=WAL is mandatory. Outbox JSONL files process transactionally. Docker restart: unless-stopped.

    Backups:

        Tier 1 (DBs & Outbox): HyperBackup to local USB (Nightly, P0) + Restic to Backblaze B2 (Nightly, P2).

        Tier 2 (Evidence): HyperBackup to local USB only.

        Restore Drill: Requires spinning up a container against a restored SQLite file to validate.

16. Resource and Cost Model

    Hardware Impact (8 GB DS923+):

        DSM + 5 Clanks + FastAPI + Ingestion: ~3.5 GB RAM.

        Verdict: Highly safe. Remaining ~4.5 GB acts as OS disk cache for SQLite FTS5.

    Cloud Costs: < $2/mo (Backblaze B2 storage). Tailscale and GitHub Actions are Free Tier.

    VPS Fallback: Hetzner Cloud CPX21 ($6.50/mo, 3 vCPU, 4GB RAM) can run the entire platform.

17. Migration Roadmap
Stage 1: Outbox Survival (P0 - August 3-8)
Parameter	Specification
Entry Criteria	Code freeze on features.
Exit Criteria	Clanks running on NAS, writing valid JSONL to Outbox.
Tests	JSON envelope validation, WAL mode active.
Rollback	Revert clank containers to previous commit.
Implementation	Claude Code (Refactoring scrapers).
Stage 2: Windows Desktop Cutover (P0 - August 9-14)
Parameter	Specification
Entry Criteria	Stage 1 soak test passes 48h.
Exit Criteria	Windows PC powered off. Tailscale SSH from Mac verified.
Tests	Power cycle NAS, verify containers boot and resume outbox writing.
Rollback	Power Windows PC back on; manually copy sqlite files back.
Implementation	Human / Infrastructure Setup.
Stage 3: Central Store & Ingestion (P1 - August 15-22)
Parameter	Specification
Entry Criteria	Cutover successful, data safely buffering in Outbox.
Exit Criteria	Ingestion worker processing files into Central SQLite.
Tests	Idempotency tests, malformed JSON tests.
Rollback	Stop worker, delete central DB, resume Outbox buffering.
Implementation	Codex.
Stage 4: Fleet API & Desktop UI (P2 - August 23+)
Parameter	Specification
Entry Criteria	Central Store populated.
Exit Criteria	PySide6 app can view queue and mutate EditorialState.
Tests	API Auth tests, UI caching tests.
Rollback	Downgrade client version.
Implementation	Claude Code.
18. Production-Readiness Checklist (Pre-Cutover)

    [ ] clank-runtime.py writes .jsonl files to /shared/outbox/.

    [ ] SQLite WAL mode active on all Domain DBs.

    [ ] No Windows-specific dependencies (os.name == 'nt') exist in clank code.

    [ ] Tailscale mesh connects Mac, Linux Dell, and NAS.

    [ ] HyperBackup snapshot successfully verified via local restore drill.

19. Risk Register
#	Risk	Likelihood	Impact	Mitigation	Contingency	Owner
1	Lost Soak Data	Low	High	Backup domain DBs before touching containers.	Fallback to manual SQL export.	Human
2	DB Corruption on Power Cut	Med	High	UPS + SQLite WAL mode mandatory.	Restore from HyperBackup.	Infra
3	Ingestion Backlog	Low	Med	Outbox handles infinite buffering safely.	Scale Ingestion Worker batches.	Shared
4	Agent Code Conflicts	High	Med	Strict one-agent-per-branch governance.	ChatGPT rejects conflicting PRs.	ChatGPT
20. ADRs (Architecture Decision Records)
#	Decision	Context	Status
1	JSONL Outbox Ingestion	Need reliable cross-container ingestion without data loss.	Accepted (P0)
2	SQLite Central Store	Need low-RAM, easily backed-up central DB for V1/V2.	Accepted (P1)
3	PySide6 Native Desktop App	Need native OS UI without Electron overhead.	Accepted (P2)
4	Tailscale Only	Need remote NAS access without opening router ports.	Accepted (P0)
5	PostgreSQL	Rejected to avoid complex server administration under deadline.	Deferred
21. First 15 Actions

    Freeze feature work on all clanks.

    Backup all Domain SQLite databases to an external drive.

    Install Tailscale on NAS, Mac, and Linux Dell.

    Create NAS directory structure (/volume1/docker/shared/outbox).

    Write clank-runtime.py (JSONL outbox writer).

    Claude Code injects clank-runtime.py into OEM Radar.

    Deploy OEM Radar to NAS; verify outbox generation.

    Inject into Free Game Tracker; deploy and verify.

    Inject into Watch Clank; deploy and verify.

    Inject into Smartphone Clank; deploy and verify.

    Inject into Chinese Tech Wire; deploy and verify.

    Suspend Semi Intel scraper (mark for repair).

    Configure Synology HyperBackup nightly snapshot.

    Perform local restore drill of Domain SQLite databases.

    Authorize August 14 Cutover.

22. August 14 Go/No-Go Checklist

You may abandon the Windows desktop ONLY IF:

    All functional clanks are running on the NAS via Docker Compose.

    Clanks are successfully dumping data into the Shared Outbox directory.

    You can SSH into the NAS via Tailscale from the Mac and Linux Dell.

    You have successfully restored a SQLite database from a NAS backup.
    (The Central API and Desktop App are explicitly NOT required for this Go/No-Go).

23. Assumptions and Unresolved Decisions

    Assumption: The Synology DS923+ UPS integration works correctly and triggers safe mode on power loss.

    Assumption: Outbox JSONL files will not exceed NAS storage limits before the Ingestion Worker is built (JSON is highly compressible; 11 days of backlog is negligible).

    Unresolved: The exact heuristic for automatically clustering Events into StoryClusters. For V2, clustering will be a manual UI action in the Desktop App until heuristics mature.

    Unresolved: Chinese text tokenization for FTS5. V2 will rely on the English-translated fields for search indexing until a specialized ICU tokenizer is implemented.

Decision Ledger

    Accepted: Modular Fleet Architecture, Tailscale, JSONL Outbox, SQLite Central Store, FastAPI, PySide6 Desktop Client, File-level backups.

    Deferred: Restic/B2 offsite backups, Historical data imports, Automated Story Clustering, Shared Python Runtime Package (PyPI).

    Rejected: Kubernetes, PostgreSQL, Kafka/Redis Streams, Embedded/Semantic Search, Browser-based Fleet UI, Shared Domain Database.