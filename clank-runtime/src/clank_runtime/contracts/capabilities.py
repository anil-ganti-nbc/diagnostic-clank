"""Canonical capability-state vocabulary (P-4.1 hardening, v0.2 §3 debt).

ONE machine-readable contract for adapter capability statements. Adapters
emit ``CapabilityState`` values with an evidence reference; Motherclank
validates against this enum and preserves UNKNOWN verbatim - never coercing.

Serialized values are lowercase strings; existing adapter-plane
capability_states() emitters already use these exact spellings, so
adoption is additive with no migration coercion. Historical serialized
evidence remains historical: unknown legacy values are reported, never
rewritten.
"""

from __future__ import annotations

from enum import StrEnum


class CapabilityState(StrEnum):
    """Evidence-bearing capability state. The distinction that matters most:

    UNSUPPORTED      - the substrate does not exist in this Clank's design.
    UNKNOWN_OR_UNVERIFIED - a substrate may exist but no evidence proves its
    current behavior. Absence of evidence is never downgraded to either
    flavor of unsupported, and never upgraded to active.
    """

    ACTIVE = "active"
    SUPPORTED_UNCONFIGURED = "supported_unconfigured"
    SUPPORTED_UNDEPLOYED = "supported_undeployed"
    UNSUPPORTED_BY_POLICY = "unsupported_by_policy"
    UNSUPPORTED = "unsupported"
    UNKNOWN_OR_UNVERIFIED = "unknown_or_unverified"


#: Observer-plane capability domains (v0.2 §10 minimum set + observed needs).
CAPABILITY_DOMAINS = (
    "collection",
    "health",
    "events",
    "delivery",
    "qc",
    "scheduler_trace",
    "continuity",
    "survivability",
)


def is_valid_capability_state(value: str) -> bool:
    try:
        CapabilityState(value)
        return True
    except ValueError:
        return False


def validate_capability_states(states: dict) -> list[str]:
    """Validate an adapter capability_states() payload shape.

    Returns human-readable violations; empty means conformant. Missing
    domains are NOT violations here (adapters declare what they know);
    wrong-state values and non-evidenced entries ARE.
    """
    errors: list[str] = []
    if not isinstance(states, dict):
        return ["capability_states must be a mapping of domain -> statement"]
    for domain, statement in states.items():
        if not isinstance(domain, str) or not domain.strip():
            errors.append(f"invalid domain: {domain!r}")
            continue
        if not isinstance(statement, dict):
            errors.append(f"{domain}: statement must be a mapping")
            continue
        state = statement.get("state")
        if not isinstance(state, str) or not is_valid_capability_state(state):
            errors.append(f"{domain}: non-canonical state {state!r}")
        if not statement.get("evidence"):
            errors.append(f"{domain}: missing evidence reference")
    return errors
