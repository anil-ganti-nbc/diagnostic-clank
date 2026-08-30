"""Explicit Diagnostic → CVC handoff package generation.

This module only transforms an operator-authored JSON evidence description
into the committed CVC handoff shape. It writes one requested artifact and
never opens CVC, ingests evidence, changes a Diagnostic store, or changes a
support/ratification decision.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "diagnostic-to-cvc-handoff.v0.1"
_REQUIRED = (
    "source_clank", "incident_id", "incident_date", "historical_verdict",
    "report_artifact_reference", "affected_components", "root_cause",
    "first_failed_gate", "remediation_evidence", "candidate_lesson",
)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _source_provenance(source: dict[str, Any]) -> dict[str, Any]:
    value = source.get("provenance")
    return value if isinstance(value, dict) else {}


def create_handoff(
    input_path: Path | str,
    output_path: Path | str,
    *,
    source_repository: str | None = None,
    source_revision: str | None = None,
) -> dict[str, Any]:
    """Create one validated handoff package from an operator-authored JSON file."""
    input_file = Path(input_path).resolve()
    output_file = Path(output_path).resolve()
    try:
        source = json.loads(input_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"handoff source is not readable JSON: {input_file}: {exc}") from exc
    if not isinstance(source, dict):
        raise ValueError("handoff source must be a JSON object")
    missing = [field for field in _REQUIRED if field not in source]
    if missing:
        raise ValueError(f"handoff source missing required field(s): {', '.join(missing)}")

    try:
        incident_date = date.fromisoformat(_text(source["incident_date"], "incident_date")).isoformat()
    except ValueError as exc:
        raise ValueError("incident_date must be an ISO date (YYYY-MM-DD)") from exc
    components = source["affected_components"]
    if not isinstance(components, list) or not components or any(
        not isinstance(item, str) or not item.strip() for item in components
    ):
        raise ValueError("affected_components must be a non-empty list of strings")
    remediation = source["remediation_evidence"]
    if not isinstance(remediation, dict) or not isinstance(remediation.get("available"), bool):
        raise ValueError("remediation_evidence.available must be boolean")
    references = remediation.get("references")
    if not isinstance(references, list) or any(
        not isinstance(item, str) or not item.strip() for item in references
    ):
        raise ValueError("remediation_evidence.references must be a list of strings")

    provenance = _source_provenance(source)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source_clank": _text(source["source_clank"], "source_clank"),
        "incident_id": _text(source["incident_id"], "incident_id"),
        "incident_date": incident_date,
        "historical_verdict": _text(source["historical_verdict"], "historical_verdict"),
        "report_artifact_reference": _text(source["report_artifact_reference"], "report_artifact_reference"),
        "affected_components": [item.strip() for item in components],
        "root_cause": _text(source["root_cause"], "root_cause"),
        "first_failed_gate": _text(source["first_failed_gate"], "first_failed_gate"),
        "remediation_evidence": {
            "available": remediation["available"],
            "references": [item.strip() for item in references],
        },
        "candidate_lesson": _text(source["candidate_lesson"], "candidate_lesson"),
        "provenance": {
            "source_repository": _text(
                source_repository or provenance.get("source_repository") or "diagnostic-clank",
                "provenance.source_repository",
            ),
            "source_revision": _text(
                source_revision or provenance.get("source_revision") or "UNKNOWN",
                "provenance.source_revision",
            ),
            "artifact_sha256": hashlib.sha256(input_file.read_bytes()).hexdigest(),
            "captured_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        },
    }
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload
