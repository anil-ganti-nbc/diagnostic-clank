"""Read-only Fleet adapters for Stage 1A."""

from __future__ import annotations

from clank_fleet.adapters.feature_phone import FeaturePhoneAdapter
from clank_fleet.adapters.oem_radar import OemRadarAdapter

__all__ = ["FeaturePhoneAdapter", "OemRadarAdapter"]
