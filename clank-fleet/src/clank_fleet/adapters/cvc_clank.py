"""Read-only observer adapter for the institutional-memory CVC Clank.

CVC is not a collector lane. Its health is corpus/integrity health and its
execution model is operator-triggered. The adapter imports CVC's bounded
observer module directly when a local CVC root is supplied; it never shells
out, writes CVC state, or exposes mutable operations.
"""
from __future__ import annotations

import sys
import importlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from clank_runtime.contracts.adapter import AdapterCapabilities, AdapterDescriptor, AdapterStatus
from clank_runtime.contracts.enums import OperationalState, ReleaseChannel
from clank_runtime.contracts.health import HealthPayload
from clank_runtime.version import ADAPTER_CONTRACT_VERSION

CLANK_ID = "cvc-clank"
CVC_REPOSITORY = "https://github.com/anil-ganti-nbc/cvc-clank"


class CVCClankAdapter:
    """Expose only the CVC observer surface to Diagnostic/Motherclank."""

    def __init__(
        self,
        *,
        db_path: Path | str,
        root_path: Path | str | None = None,
        clank_version: str = "0.1.0",
    ) -> None:
        # db_path remains part of the common adapter constructor. For CVC it
        # is a non-database sentinel unless an explicit root_path is supplied.
        self.db_path = Path(db_path)
        self.root_path = Path(root_path).resolve() if root_path else self.db_path.resolve()
        self.clank_version = clank_version

    def identity(self) -> AdapterDescriptor:
        return AdapterDescriptor(
            contract_version=ADAPTER_CONTRACT_VERSION,
            clank_id=CLANK_ID,
            clank_version=self.clank_version,
            release_channel=ReleaseChannel.PRODUCTION,
            capabilities=self.capabilities(),
            display_name="CVC Clank",
            description="Cross-Clank institutional evidence memory; integrity observer only",
        )

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_identity=True,
            supports_status=True,
            supports_health=True,
            supports_last_run=True,
            supports_manual_run=False,
            supports_telemetry=False,
            supports_delivery_accounting=False,
            supports_version=True,
            supports_replay=False,
            supports_local_fallback=False,
        )

    def _load_snapshot(self) -> tuple[dict[str, Any] | None, str | None]:
        if not self.root_path.is_dir():
            return None, f"CVC root unavailable: {self.root_path}"
        src = self.root_path / "src"
        if not src.is_dir():
            return None, f"CVC source unavailable: {src}"
        source = str(src)
        if source not in sys.path:
            sys.path.insert(0, source)
        try:
            # Keep an explicitly selected local root authoritative if a
            # process has observed another CVC checkout earlier in its life.
            for module_name in tuple(sys.modules):
                if module_name == "cvc" or module_name.startswith("cvc."):
                    del sys.modules[module_name]
            importlib.invalidate_caches()
            from cvc.observer import observer_snapshot

            return observer_snapshot(self.root_path), None
        except Exception as exc:  # noqa: BLE001 - one lane fails safely
            return None, f"CVC observer failed: {type(exc).__name__}: {exc}"

    @staticmethod
    def _state(snapshot: dict[str, Any]) -> OperationalState:
        health = snapshot.get("health", {})
        if health.get("corpus_integrity") == "FAIL":
            return OperationalState.FAILED
        if not health.get("runtime_state_readable", False):
            return OperationalState.DEGRADED
        return OperationalState.HEALTHY

    @staticmethod
    def _extensions(snapshot: dict[str, Any]) -> dict[str, Any]:
        return {
            "health_semantics": "integrity",
            "recency_policy": "NONE",
            "lifecycle": "OPERATIONAL",
            "execution_model": "OPERATOR_TRIGGERED",
            "scheduling": "NONE",
            "authority": "OBSERVER",
            "observer_schema_version": snapshot.get("schema_version"),
            "summary": snapshot.get("summary", {}),
        }

    def status(self) -> AdapterStatus:
        now = datetime.now(UTC)
        snapshot, error = self._load_snapshot()
        if snapshot is None:
            return AdapterStatus(
                clank_id=CLANK_ID,
                operational_state=OperationalState.UNKNOWN,
                release_channel=ReleaseChannel.PRODUCTION,
                version=self.clank_version,
                location="unavailable",
                message=error,
                is_stale=True,
                observed_at=now,
                extensions={
                    "health_semantics": "integrity",
                    "recency_policy": "NONE",
                    "lifecycle": "OPERATIONAL",
                    "execution_model": "OPERATOR_TRIGGERED",
                    "scheduling": "NONE",
                    "authority": "OBSERVER",
                },
            )
        return AdapterStatus(
            clank_id=CLANK_ID,
            operational_state=self._state(snapshot),
            release_channel=ReleaseChannel.PRODUCTION,
            version=self.clank_version,
            location="local",
            message="CVC integrity observer; no scheduled run is expected",
            is_stale=False,
            observed_at=now,
            extensions=self._extensions(snapshot),
        )

    def health(self) -> HealthPayload:
        now = datetime.now(UTC)
        snapshot, error = self._load_snapshot()
        if snapshot is None:
            return HealthPayload(
                clank_id=CLANK_ID,
                overall_status=OperationalState.UNKNOWN,
                freshness="unknown",
                warnings=[error or "CVC observer unavailable"],
                observed_at=now,
                extensions={"health_semantics": "integrity", "recency_policy": "NONE"},
            )
        cvc_health = snapshot.get("health", {})
        warnings: list[str] = []
        if cvc_health.get("corpus_integrity") == "FAIL":
            warnings.append(f"CVC corpus integrity failed ({cvc_health.get('failure_count', 0)} failure(s))")
        warnings.extend(str(item) for item in cvc_health.get("state_read_errors", []))
        return HealthPayload(
            clank_id=CLANK_ID,
            overall_status=self._state(snapshot),
            run_status="integrity_verification",
            freshness="unknown",
            warnings=warnings,
            observed_at=now,
            extensions=self._extensions(snapshot),
        )

    def last_run(self) -> dict[str, Any]:
        return {
            "supported": False,
            "reason": "CVC is operator-triggered and has no scheduler or periodic run",
            "policy": "NONE",
        }

    def capability_states(self) -> dict[str, dict[str, str]]:
        return {
            "collection": {
                "state": "unsupported_by_policy",
                "evidence": "CVC stores institutional evidence; it is not a fleet collector.",
            },
            "health": {
                "state": "active",
                "evidence": "CVC exposes corpus-integrity and runtime-state readability through observer_snapshot.",
            },
            "evidence_memory": {
                "state": "active",
                "evidence": "CVC exposes its frozen board, triggers, and bounded append-only activity summary.",
            },
            "delivery": {
                "state": "unsupported_by_policy",
                "evidence": "CVC does not own notification or delivery execution.",
            },
            "scheduler": {
                "state": "unsupported_by_policy",
                "evidence": "CVC execution model is OPERATOR_TRIGGERED and scheduling is NONE.",
            },
            "continuity": {
                "state": "unknown_or_unverified",
                "evidence": "The observer does not infer cross-host continuity from corpus state.",
            },
        }

    def observer_snapshot(self) -> dict[str, Any]:
        snapshot, error = self._load_snapshot()
        if snapshot is not None:
            return snapshot
        return {
            "schema_version": "cvc-observer.v0.1",
            "identity": {"clank_id": CLANK_ID, "display_name": "CVC Clank", "repo": CVC_REPOSITORY},
            "health": {"corpus_integrity": "UNKNOWN", "runtime_state_readable": False, "error": error},
            "summary": {"status": "UNKNOWN", "integrity": "UNKNOWN"},
        }

    def telemetry(self) -> list[dict[str, Any]]:
        return []

    def source_summary(self) -> list[dict[str, Any]]:
        # CVC has no collector sources. An empty list is not a healthy-source
        # count; Motherclank applies the declared integrity semantics.
        return []
