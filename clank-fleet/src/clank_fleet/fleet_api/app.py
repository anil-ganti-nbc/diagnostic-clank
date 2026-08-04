"""FastAPI application factory for the Fleet API shell (Stage 0)."""

from __future__ import annotations

from fastapi import FastAPI

from clank_fleet import API_CONTRACT_VERSION, __version__
from clank_fleet.fleet_api.routes import register_routes


def create_app() -> FastAPI:
    """Create the Stage 0 Fleet API application shell.

    This factory registers route stubs only. No production behavior is wired.
    """
    app = FastAPI(
        title="Clank Fleet API",
        description=(
            "Stage 0 skeleton. Behavior endpoints return HTTP 501. "
            "Only the process-level ping is operational."
        ),
        version=__version__,
        openapi_tags=[
            {"name": "system", "description": "Process-level shell checks"},
            {"name": "fleet", "description": "Fleet-wide operations (not implemented)"},
            {"name": "clanks", "description": "Per-clank operations (not implemented)"},
            {"name": "records", "description": "Newsroom records (not implemented)"},
            {"name": "events", "description": "Events (not implemented)"},
            {"name": "entities", "description": "Entities (not implemented)"},
            {"name": "evidence", "description": "Evidence (not implemented)"},
            {"name": "review", "description": "Editorial review (not implemented)"},
            {"name": "backups", "description": "Backups (not implemented)"},
            {"name": "deployments", "description": "Deployments (not implemented)"},
            {"name": "ingestion", "description": "Ingestion (not implemented)"},
            {"name": "search", "description": "Search (not implemented)"},
        ],
    )
    app.state.api_contract_version = API_CONTRACT_VERSION
    register_routes(app)
    return app
