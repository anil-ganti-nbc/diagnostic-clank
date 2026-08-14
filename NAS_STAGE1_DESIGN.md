# NAS Stage 1 Design

**No migration in this phase.** Design only.

## Principles

1. Each Clank remains an independent runtime (container or process).
2. Production SQLite on **local** volumes (not network mounts).
3. Secrets via environment / Docker secrets — never image layers.
4. Fleet reads health/telemetry via adapters; does not embed scrapers.
5. Timezone: process UTC; human display may use IST.

## Container boundaries

- One service (or one compose service) per production Clank.
- Named volumes for DB and durable state.
- Restart policy: `unless-stopped` or equivalent.
- Resource limits per Clank (CPU/memory) to isolate noisy neighbours.
- Healthcheck: process alive + optional `clank health` exit code.

## SQLite guidance

- WAL mode recommended.
- One writer assumption; overlap → skip or lock.
- Graceful shutdown before volume snapshot.
- Backup: stop or online backup API → integrity check → off-NAS copy.
- Restore: test on non-production volume before declaring Tier 2 backup valid.

## Scheduling

- Prefer in-container cron/systemd timer **or** host scheduler invoking `docker compose run`.
- Record `host_id` / container id in telemetry.

## Networking

- Tailscale or equivalent private path to Fleet API and desktop clients.
- Dashboards bound to localhost or private interface only unless authenticated.

## Upgrades / rollback

- Image tags immutable (digest preferred).
- Rollback = previous image + previous volume snapshot.
- Never migrate schema without Alembic/migration note in Clank.

## Adapters

Stage 1 minimum: identity, status, health, version. Telemetry export may be file-based (JSONL) initially.
