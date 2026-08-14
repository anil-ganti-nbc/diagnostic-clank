"""Build FleetRegistry from config / environment."""

from __future__ import annotations

import os
from pathlib import Path

from clank_fleet.adapters.feature_phone import FeaturePhoneAdapter
from clank_fleet.adapters.oem_radar import OemRadarAdapter
from clank_fleet.registry.core import FleetRegistry


def build_default_registry(
    *,
    oem_db: Path | str | None = None,
    feature_phone_db: Path | str | None = None,
) -> FleetRegistry:
    registry = FleetRegistry()
    oem_path = Path(
        oem_db
        or os.environ.get("OEM_RADAR_DB", "data/oem-radar.db")
    )
    fp_path = Path(
        feature_phone_db
        or os.environ.get("FEATURE_PHONE_CLANK_DB", "data/feature_phone_clank.db")
    )
    registry.register(OemRadarAdapter(db_path=oem_path))
    registry.register(FeaturePhoneAdapter(db_path=fp_path))
    return registry
