"""Enumerations for operational, release, and ingestion states.

Stage 0.5 draft only. Do not treat as final production taxonomy.
Semantic values are stable; additional members may be added in later stages
with a contract version bump.
"""

from __future__ import annotations

from enum import StrEnum


class OperationalState(StrEnum):
    """High-level operational state of a clank process.

    Separate from :class:`ReleaseChannel` (maturity of the deployment).
    """

    STARTING = "starting"
    HEALTHY = "healthy"
    IDLE = "idle"
    DEGRADED = "degraded"
    FAILED = "failed"
    PAUSED = "paused"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class ReleaseChannel(StrEnum):
    """Release channel classification for a clank deployment.

    Operational state is independent of release maturity (Amendment 7).
    """

    EXPERIMENTAL = "experimental"
    SOAKING = "soaking"
    STAGING = "staging"
    PRODUCTION = "production"
    REPAIR = "repair"
    DEPRECATED = "deprecated"


class IngestionState(StrEnum):
    """Ingestion pipeline state relative to expected freshness.

    Placeholder until ingestion is implemented (post-P0).
    """

    CURRENT = "current"
    DELAYED = "delayed"
    BACKLOGGED = "backlogged"
    STALLED = "stalled"
    REPLAYING = "replaying"
    QUARANTINED = "quarantined"
    UNKNOWN = "unknown"
