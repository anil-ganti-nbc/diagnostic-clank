"""Application-result attestation: extractors turning positively observed
invocation output into canonical execution_result values (P-4.2).

Ownership (ADR-0012): application-specific output interpretation lives in
the Diagnostic Clank adapter/probe plane - NEVER in Motherclank core.
Motherclank only validates and consumes the resulting canonical fields.

Contract every extractor must honor:

- The participant's OWN documented semantics are the only basis for a
  non-null classification. Output text alone proves nothing until the
  producing code path has been traced and its meaning established.
- Unparseable / unrecognized output -> execution_result None (UNKNOWN).
  Absence of a participant record NEVER becomes no_work_due or failed.
- Exit codes may distinguish failed/completed ONLY where the participant
  contract makes that interpretation valid (e.g., OEM Radar reserves exit
  code 2 for lock contention, which is by-design behavior - not failure).
- Every result carries provenance: extractor identity/version plus the
  matched evidence excerpt (bounded, never whole logs).
"""

from __future__ import annotations

from typing import Any, Protocol

EXTRACTOR_CONTRACT_VERSION = 1


class ExecutionResultExtractor(Protocol):
    """A clank-specific output interpreter owned by the adapter plane."""

    id: str
    version: int

    def extract(self, output_text: str | None,
                *, exit_code: int | None = None) -> dict[str, Any]:
        """Return {execution_result, execution_detail, ...provenance} or a
        dict with execution_result=None when the evidence is insufficient."""
        ...


_REGISTRY: dict[str, Any] = {}

#: clank_id -> extractor submodule slug (lazy import; the architecture test
#: forbids direct adapter imports from shared planes).
_SLUGS = {"oem-radar": "oem_radar"}


def register(clank_id: str, extractor: Any) -> None:
    _REGISTRY[clank_id] = extractor


def get_extractor(clank_id: str):
    """Extractor for one Clank, or None when no attestation contract exists
    (Motherclank treats that as UNKNOWN - never guesses). Lazy import keeps
    this shared plane free of literal adapter imports."""
    if clank_id in _REGISTRY:
        return _REGISTRY[clank_id]
    slug = _SLUGS.get(clank_id)
    if slug is None:
        return None
    import importlib  # noqa: PLC0415 - lazy by design

    module = importlib.import_module(f".{slug}", __name__)
    extractor = getattr(module, "EXTRACTOR")
    register(clank_id, extractor)
    return extractor


def registered_ids() -> tuple[str, ...]:
    return tuple(sorted(set(_REGISTRY) | set(_SLUGS)))

# Built-in extractor submodules are discovered lazily via get_extractor()
# (architecture test forbids literal adapter imports from shared planes).
