from __future__ import annotations

import hashlib
import json
from pathlib import Path

from diagnostic_clank.handoff import create_handoff


def test_create_handoff_is_explicit_and_supports_success_evidence(tmp_path: Path) -> None:
    source = tmp_path / "success.json"
    source.write_text(json.dumps({
        "source_clank": "smartwatch-clank",
        "incident_id": "RESTORE-2026-08-30",
        "incident_date": "2026-08-30",
        "historical_verdict": "SUCCESSFUL_RESTORE",
        "report_artifact_reference": "reports/restore.md",
        "affected_components": ["smartwatch-clank", "restore procedure"],
        "root_cause": "NOT_APPLICABLE — positive evidence package",
        "first_failed_gate": "NOT_APPLICABLE — no failed gate",
        "remediation_evidence": {"available": True, "references": ["tests/test_restore.py"]},
        "candidate_lesson": "A bounded restore replay preserved the documented state lineage.",
        "provenance": {"source_repository": "https://github.com/example/diagnostic"},
    }, indent=2), encoding="utf-8")
    output = tmp_path / "handoff.json"

    payload = create_handoff(source, output, source_revision="abc1234")

    assert output.exists()
    assert payload["schema_version"] == "diagnostic-to-cvc-handoff.v0.1"
    assert payload["historical_verdict"] == "SUCCESSFUL_RESTORE"
    assert payload["provenance"]["artifact_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert payload["provenance"]["source_revision"] == "abc1234"
    assert "ingest" not in payload


def test_handoff_does_not_touch_a_cvc_state_directory(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text(json.dumps({
        "source_clank": "diagnostic-clank",
        "incident_id": "INC-1",
        "incident_date": "2026-08-30",
        "historical_verdict": "HISTORICAL_EVIDENCE",
        "report_artifact_reference": "reports/incident.md",
        "affected_components": ["fleet"],
        "root_cause": "UNKNOWN",
        "first_failed_gate": "UNKNOWN",
        "remediation_evidence": {"available": False, "references": []},
        "candidate_lesson": "Review whether this evidence maps to an existing trigger.",
    }), encoding="utf-8")
    cvc_state = tmp_path / "cvc" / "state"
    cvc_state.mkdir(parents=True)
    marker = cvc_state / ".gitkeep"
    marker.write_text("", encoding="utf-8")

    create_handoff(source, tmp_path / "handoff.json")

    assert list(cvc_state.iterdir()) == [marker]
