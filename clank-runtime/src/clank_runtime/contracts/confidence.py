"""Confidence dimension names (Stage 0.5).

Architecture Amendment 11: never collapse confidence into a single score.
These are *names* only — no scoring logic is implemented here.
"""

from __future__ import annotations

from typing import Final

# Canonical dimension keys for EventEnvelope.confidence_dimensions
SOURCE_RELIABILITY: Final = "source_reliability"
EVIDENCE_STRENGTH: Final = "evidence_strength"
CORROBORATION: Final = "corroboration"
FRESHNESS: Final = "freshness"
PARSER_QUALITY: Final = "parser_quality"
INGESTION_QUALITY: Final = "ingestion_quality"
ENTITY_CERTAINTY: Final = "entity_certainty"

KNOWN_CONFIDENCE_DIMENSIONS: Final[frozenset[str]] = frozenset(
    {
        SOURCE_RELIABILITY,
        EVIDENCE_STRENGTH,
        CORROBORATION,
        FRESHNESS,
        PARSER_QUALITY,
        INGESTION_QUALITY,
        ENTITY_CERTAINTY,
    }
)
