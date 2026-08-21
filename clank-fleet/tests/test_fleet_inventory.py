from __future__ import annotations

import re
from pathlib import Path

import yaml


INVENTORY = Path(__file__).parents[1] / "inventories" / "fleet.yaml"
EXPECTED = {
    "watch-clank", "diagnostic-clank", "clank-architecture", "smartwatch-clank",
    "korean-tech-wire", "feature-phone-clank", "unified-clank-platform",
    "tablet-clank", "chinese-tech-wire", "smartphone-clank",
    "semiconductor-intelligence", "free-game-tracker", "oem-radar",
}
REQUIRED_TRUTH = {
    "deployed_sha", "artifact_digest", "environment", "deployment_owner",
    "scheduler", "database", "credentials_owner", "notification", "backup",
    "rollback_target",
}


def _load() -> dict:
    return yaml.safe_load(INVENTORY.read_text(encoding="utf-8"))


def test_inventory_is_complete_and_has_no_silent_omissions() -> None:
    inventory = _load()
    declared = {row["repository"].rsplit("/", 1)[-1] for row in inventory["systems"]}
    assert set(inventory["expected_repositories"]) == EXPECTED
    assert declared == EXPECTED
    assert len(inventory["systems"]) == len(EXPECTED)


def test_inventory_separates_source_and_deployment_truth() -> None:
    for row in _load()["systems"]:
        assert re.fullmatch(r"[0-9a-f]{40}", row["source_sha"])
        assert REQUIRED_TRUTH <= row.keys()
        assert row["classification"] in {"UNVERIFIED_PRODUCTION", "PROTOTYPE"}
        assert row["promotion_eligible"] is False
        if row["deployed_sha"] != "UNKNOWN":
            assert re.fullmatch(r"[0-9a-f]{40}", row["deployed_sha"])


def test_phase_zero_promotion_freeze_is_explicit() -> None:
    policy = _load()["promotion_policy"]
    assert policy["frozen"] is True
    assert policy["reason"]
