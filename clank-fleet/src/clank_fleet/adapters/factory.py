"""Build FleetRegistry from config / environment."""

from __future__ import annotations

import os
from pathlib import Path

from clank_fleet.adapters.feature_phone import FeaturePhoneAdapter
from clank_fleet.adapters.korean_tech_wire import KoreanTechWireAdapter
from clank_fleet.adapters.oem_radar import OemRadarAdapter
from clank_fleet.adapters.smartphone_clank import SmartphoneClankAdapter
from clank_fleet.adapters.watch_clank import WatchClankAdapter
from clank_fleet.registry.core import FleetRegistry


def build_default_registry(
    *,
    oem_db: Path | str | None = None,
    feature_phone_db: Path | str | None = None,
    watch_db: Path | str | None = None,
    smartphone_db: Path | str | None = None,
    korean_tech_wire_db: Path | str | None = None,
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
    watch_path = Path(
        watch_db
        or os.environ.get("WATCH_CLANK_DB", "data/watch_clank.db")
    )
    sphone_path = Path(
        smartphone_db
        or os.environ.get("SMARTPHONE_CLANK_DB", "data/smartphone_clank.db")
    )
    ktw_path = Path(
        korean_tech_wire_db
        or os.environ.get("KOREAN_TECH_WIRE_DB", "data/korean_tech_wire.db")
    )
    registry.register(OemRadarAdapter(db_path=oem_path))
    registry.register(FeaturePhoneAdapter(db_path=fp_path))
    registry.register(WatchClankAdapter(db_path=watch_path))
    registry.register(SmartphoneClankAdapter(db_path=sphone_path))
    registry.register(KoreanTechWireAdapter(db_path=ktw_path))
    return registry
