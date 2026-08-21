from __future__ import annotations

import copy
import datetime as dt
from pathlib import Path

from clank_fleet.inventory import EXPECTED_REPOSITORIES, evaluate_health, load_inventory, validate_inventory


INVENTORY = Path(__file__).parents[1] / "inventories" / "fleet.yaml"
NOW = dt.datetime(2026, 8, 21, 12, tzinfo=dt.UTC)


def _load() -> dict:
    return load_inventory(INVENTORY)


def _deployment(instance_id: str = "semint-hetzner-stage-01") -> dict:
    return {
        "instance_id": instance_id,
        "repository": "semiconductor-intelligence",
        "deployment_state": "RUNNING",
        "environment": "staging",
        "failure_domain": "hetzner-stage",
        "location_type": "HETZNER",
        "location": "fsn1",
        "host": "stage-01",
        "deployed_commit_sha": "a" * 40,
        "artifact_digest": "sha256:" + "b" * 64,
        "source_branch_or_tag": "phase0-test",
        "service_identity": "semint-stage",
        "working_directory_or_container": "/srv/semint",
        "runtime": {"implementation": "CPython", "version": "3.12.5"},
        "dependency_lock": {"file": "uv.lock", "digest": "sha256:test", "matches": True},
        "database_path": "/srv/semint/state.db",
        "evidence_path": "/srv/semint/evidence",
        "scheduler": {"type": "TaskScheduler", "authority": "semint-stage", "owner": "ops", "enabled": True},
        "notification": {"authority": "semint-stage-test", "owner": "ops", "enabled": True},
        "backup": {"location": "/backup/semint", "last_verified_utc": "2026-08-21T10:00:00Z"},
        "health": {
            "scheduler_invocation_utc": "2026-08-21T11:30:00Z",
            "application_start_utc": "2026-08-21T11:30:01Z",
            "successful_job_commit_utc": "2026-08-21T11:35:00Z",
            "source_freshness_utc": "2026-08-21T11:34:00Z",
            "last_job_status": "SUCCESSFUL",
            "heartbeat_stale_after_seconds": 7200,
        },
        "secrets": {"owner": "ops", "storage_mechanism": "secret-manager"},
        "rollback_artifact": "sha256:" + "c" * 64,
        "last_operator_verification": {"operator": "test", "observed_at_utc": "2026-08-21T11:40:00Z"},
        "promotion_eligible": False,
    }


def test_exact_phase_zero_repository_set_is_represented() -> None:
    inventory = _load()
    assert set(inventory["expected_repositories"]) == EXPECTED_REPOSITORIES
    assert {row["name"] for row in inventory["repositories"]} == EXPECTED_REPOSITORIES
    assert validate_inventory(inventory, now=NOW)["status"] == "INVENTORY_INCOMPLETE"


def test_missing_repository_is_inventory_incomplete() -> None:
    inventory = _load()
    inventory["repositories"] = inventory["repositories"][:-1]
    report = validate_inventory(inventory, now=NOW)
    assert report["status"] == "INVENTORY_INCOMPLETE"
    assert any(item["code"] == "INVENTORY_INCOMPLETE" for item in report["findings"])


def test_unknown_deployment_is_never_healthy() -> None:
    report = validate_inventory(_load(), now=NOW)
    unknown = [item for item in report["findings"] if item["code"] == "UNKNOWN_DEPLOYMENT_STATE"]
    assert len(unknown) == 12


def test_duplicate_scheduler_and_notification_authority_are_visible() -> None:
    inventory = _load()
    inventory["deployments"] = [_deployment("first"), _deployment("second")]
    report = validate_inventory(inventory, now=NOW)
    assert report["status"] == "INVENTORY_CONFLICT"
    codes = {item["code"] for item in report["findings"]}
    assert "DUPLICATE_SCHEDULER_AUTHORITY" in codes
    assert "DUPLICATE_NOTIFICATION_AUTHORITY" in codes


def test_stale_failed_and_missing_jobs_are_distinct() -> None:
    stale = _deployment()
    stale["health"]["successful_job_commit_utc"] = "2026-08-21T08:00:00Z"
    failed = copy.deepcopy(stale)
    failed["health"]["last_job_status"] = "FAILED"
    missing = copy.deepcopy(stale)
    missing["health"]["successful_job_commit_utc"] = "UNKNOWN"
    missing["health"]["last_job_status"] = "UNKNOWN"
    assert evaluate_health(stale, now=NOW)["state"] == "STALE_HEARTBEAT"
    assert evaluate_health(failed, now=NOW)["state"] == "FAILED_JOB"
    assert evaluate_health(missing, now=NOW)["state"] == "MISSING_JOB"


def test_complete_evidenced_deployment_can_be_healthy() -> None:
    assert evaluate_health(_deployment(), now=NOW)["state"] == "HEALTHY"
