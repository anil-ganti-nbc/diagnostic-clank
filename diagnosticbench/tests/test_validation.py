from pathlib import Path

import yaml


CASES = Path(__file__).parents[1] / "cases"


def test_all_related_case_ids_resolve():
    docs = {}
    for path in CASES.glob("DB-*.yaml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        docs[data["case_id"]] = data
    missing = []
    for case in docs.values():
        for relationship in case.get("relationships", []):
            target = relationship.get("related_case_id")
            if target not in docs:
                missing.append(f"{case['case_id']} -> {target}")
    assert not missing, "Dangling DiagnosticBench relationships: " + ", ".join(missing)
