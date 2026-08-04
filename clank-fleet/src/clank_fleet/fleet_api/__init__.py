"""Fleet API application shell (Stage 0).

All behavior endpoints return HTTP 501 Not Implemented.
Only the process-level ping may return 200.
"""
from __future__ import annotations

from clank_fleet.fleet_api.app import create_app

__all__ = ["create_app"]
