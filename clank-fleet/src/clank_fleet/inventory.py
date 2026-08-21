"""Phase 0 fleet inventory validation.

The validator never converts missing host evidence into a healthy state. It is
deliberately independent of the API so operators and CI can validate the same
ledger without starting a service.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

UNKNOWN = "UNKNOWN"
EXPECTED_REPOSITORIES = frozenset(
    {
        "watch-clank",
        "diagnostic-clank",
        "clank-architecture",
        "smartwatch-clank",
        "korean-tech-wire",
        "feature-phone-clank",
        "unified-clank-platform",
        "tablet-clank",
        "chinese-tech-wire",
        "smartphone-clank",
        "semiconductor-intelligence",
        "free-game-tracker",
        "oem-radar",
    }
)

REQUIRED_DEPLOYMENT_FIELDS = frozenset(
    {
        "instance_id",
        "repository",
        "environment",
        "failure_domain",
        "location_type",
        "location",
        "host",
        "deployed_commit_sha",
        "artifact_digest",
        "source_branch_or_tag",
        "service_identity",
        "working_directory_or_container",
        "runtime",
        "dependency_lock",
        "database_path",
        "evidence_path",
        "scheduler",
        "notification",
        "backup",
        "health",
        "secrets",
        "rollback_artifact",
        "last_operator_verification",
        "promotion_eligible",
    }
)


def _finding(code: str, subject: str, detail: str) -> dict[str, str]:
    return {"code": code, "subject": subject, "detail": detail}


def _parse_time(value: object) -> dt.datetime | None:
    if value in (None, "", UNKNOWN):
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC)


def evaluate_health(
    deployment: dict[str, Any], *, now: dt.datetime
) -> dict[str, str]:
    """Return a non-overlapping operational state for one deployment."""
    health = deployment.get("health")
    if not isinstance(health, dict) or deployment.get("deployment_state", UNKNOWN) == UNKNOWN:
        return {"state": "UNKNOWN_DEPLOYMENT", "reason": "deployment evidence is unavailable"}

    job_status = health.get("last_job_status", UNKNOWN)
    if job_status == "FAILED":
        return {"state": "FAILED_JOB", "reason": "the latest observed job failed"}

    last_success = _parse_time(health.get("successful_job_commit_utc"))
    last_invocation = _parse_time(health.get("scheduler_invocation_utc"))
    if last_success is None:
        if last_invocation is not None:
            return {"state": "MISSING_JOB", "reason": "scheduler invoked without a committed success"}
        return {"state": "UNKNOWN_DEPLOYMENT", "reason": "no scheduler or job evidence"}

    stale_after = health.get("heartbeat_stale_after_seconds", UNKNOWN)
    if stale_after == UNKNOWN:
        return {"state": "UNKNOWN_DEPLOYMENT", "reason": "heartbeat threshold is unknown"}
    try:
        is_stale = now - last_success > dt.timedelta(seconds=int(stale_after))
    except (TypeError, ValueError):
        return {"state": "UNKNOWN_DEPLOYMENT", "reason": "heartbeat threshold is invalid"}
    if is_stale:
        return {"state": "STALE_HEARTBEAT", "reason": "last committed success exceeded threshold"}

    freshness = _parse_time(health.get("source_freshness_utc"))
    if freshness is None:
        return {"state": "UNKNOWN_DEPLOYMENT", "reason": "source freshness is unknown"}
    return {"state": "HEALTHY", "reason": "success heartbeat and source freshness are evidenced"}


def validate_inventory(data: dict[str, Any], *, now: dt.datetime | None = None) -> dict[str, Any]:
    now = (now or dt.datetime.now(dt.UTC)).astimezone(dt.UTC)
    findings: list[dict[str, str]] = []

    expected = set(data.get("expected_repositories") or [])
    represented = {row.get("name") for row in data.get("repositories") or []}
    for name in sorted(EXPECTED_REPOSITORIES - expected):
        findings.append(_finding("INVENTORY_INCOMPLETE", name, "missing from expected repositories"))
    for name in sorted(EXPECTED_REPOSITORIES - represented):
        findings.append(_finding("INVENTORY_INCOMPLETE", name, "missing repository catalogue entry"))
    for name in sorted(expected - EXPECTED_REPOSITORIES):
        findings.append(_finding("OUT_OF_SCOPE_REPOSITORY", name, "not in the Phase 0 set"))

    for row in data.get("repositories") or []:
        name = str(row.get("name", UNKNOWN))
        for key in ("canonical_url", "classification", "deployment_state"):
            if key not in row:
                findings.append(_finding("INVENTORY_INCOMPLETE", name, f"missing {key}"))
        if row.get("deployment_state") == UNKNOWN:
            findings.append(_finding("UNKNOWN_DEPLOYMENT_STATE", name, "host discovery not evidenced"))

    deployments = data.get("deployments") or []
    scheduler_owners: dict[str, list[str]] = defaultdict(list)
    notification_owners: dict[str, list[str]] = defaultdict(list)
    deployment_health: dict[str, dict[str, str]] = {}
    seen_ids: set[str] = set()

    for deployment in deployments:
        instance_id = str(deployment.get("instance_id", UNKNOWN))
        missing = REQUIRED_DEPLOYMENT_FIELDS - deployment.keys()
        if missing:
            findings.append(
                _finding("INVENTORY_INCOMPLETE", instance_id, f"missing fields: {', '.join(sorted(missing))}")
            )
        if instance_id in seen_ids:
            findings.append(_finding("DUPLICATE_INSTANCE_ID", instance_id, "instance ID is not unique"))
        seen_ids.add(instance_id)

        scheduler = deployment.get("scheduler") or {}
        scheduler_key = scheduler.get("authority", UNKNOWN)
        if scheduler.get("enabled") is True and scheduler_key != UNKNOWN:
            scheduler_owners[str(scheduler_key)].append(instance_id)
        notification = deployment.get("notification") or {}
        notification_key = notification.get("authority", UNKNOWN)
        if notification.get("enabled") is True and notification_key != UNKNOWN:
            notification_owners[str(notification_key)].append(instance_id)

        deployment_health[instance_id] = evaluate_health(deployment, now=now)
        if deployment.get("promotion_eligible") is not False:
            findings.append(_finding("PROMOTION_FREEZE_VIOLATION", instance_id, "promotion_eligible must be false"))

    for authority, owners in sorted(scheduler_owners.items()):
        if len(owners) > 1:
            findings.append(
                _finding("DUPLICATE_SCHEDULER_AUTHORITY", authority, ", ".join(sorted(owners)))
            )
    for authority, owners in sorted(notification_owners.items()):
        if len(owners) > 1:
            findings.append(
                _finding("DUPLICATE_NOTIFICATION_AUTHORITY", authority, ", ".join(sorted(owners)))
            )

    conflict_codes = {
        "DUPLICATE_INSTANCE_ID",
        "DUPLICATE_SCHEDULER_AUTHORITY",
        "DUPLICATE_NOTIFICATION_AUTHORITY",
        "PROMOTION_FREEZE_VIOLATION",
    }
    if any(item["code"] in conflict_codes for item in findings):
        status = "INVENTORY_CONFLICT"
    elif findings or any(item["state"] != "HEALTHY" for item in deployment_health.values()):
        status = "INVENTORY_INCOMPLETE"
    else:
        status = "INVENTORY_COMPLETE"
    return {"status": status, "findings": findings, "deployment_health": deployment_health}


def load_inventory(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("inventory root must be a mapping")
    return loaded


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the Phase 0 fleet ledger")
    parser.add_argument("inventory", type=Path)
    args = parser.parse_args()
    report = validate_inventory(load_inventory(args.inventory))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "INVENTORY_COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
