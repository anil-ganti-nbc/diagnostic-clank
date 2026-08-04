"""Route registration for Fleet API (Stage 0.5).

Every behavior route returns HTTP 501 with a consistent NotImplementedResponse.
Only GET /api/v1/system/ping may return 200, and only as a process-level shell check.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI, status
from fastapi.responses import JSONResponse

from clank_fleet.fleet_api.models import NotImplementedResponse, PingResponse

# Stable OpenAPI operation descriptions reminding agents not to implement logic here.
_STAGE_NOTE = "Stage 0.5 skeleton — returns 501. Do not implement business logic in this route."


def _not_implemented(*, detail: str | None = None) -> JSONResponse:
    body = NotImplementedResponse(
        details={"hint": detail} if detail else {},
    )
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content=body.model_dump(),
    )


def _add_stub_collection(router: APIRouter, resource_name: str) -> None:
    """Attach collection and item stubs that always return 501."""

    @router.get(
        "",
        summary=f"List {resource_name} (not implemented)",
        description=_STAGE_NOTE,
    )
    @router.get(
        "/",
        summary=f"List {resource_name} (not implemented)",
        description=_STAGE_NOTE,
        include_in_schema=False,
    )
    def collection_root() -> JSONResponse:
        return _not_implemented(detail=f"{resource_name} collection")

    @router.get(
        "/{item_id}",
        summary=f"Get {resource_name} item (not implemented)",
        description=_STAGE_NOTE,
    )
    def collection_item(item_id: str) -> JSONResponse:
        return _not_implemented(detail=f"{resource_name}/{item_id}")


def register_routes(app: FastAPI) -> None:
    """Register all Stage 0.5 route stubs with consistent naming and envelopes."""
    system = APIRouter(prefix="/api/v1/system", tags=["system"])
    fleet = APIRouter(prefix="/api/v1/fleet", tags=["fleet"])
    clanks = APIRouter(prefix="/api/v1/clanks", tags=["clanks"])
    records = APIRouter(prefix="/api/v1/records", tags=["records"])
    events = APIRouter(prefix="/api/v1/events", tags=["events"])
    entities = APIRouter(prefix="/api/v1/entities", tags=["entities"])
    evidence = APIRouter(prefix="/api/v1/evidence", tags=["evidence"])
    review = APIRouter(prefix="/api/v1/review", tags=["review"])
    backups = APIRouter(prefix="/api/v1/backups", tags=["backups"])
    deployments = APIRouter(prefix="/api/v1/deployments", tags=["deployments"])
    ingestion = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])
    search = APIRouter(prefix="/api/v1/search", tags=["search"])

    @system.get(
        "/ping",
        response_model=PingResponse,
        summary="Process-level shell check",
        description=(
            "Confirms the API process started. "
            "Does not claim fleet health, storage, ingestion, or backups."
        ),
    )
    def ping() -> PingResponse:
        return PingResponse()

    @fleet.get("", summary="Fleet root (not implemented)", description=_STAGE_NOTE)
    @fleet.get("/", include_in_schema=False)
    def fleet_root() -> JSONResponse:
        return _not_implemented(detail="fleet")

    @fleet.get("/status", summary="Fleet status (not implemented)", description=_STAGE_NOTE)
    def fleet_status() -> JSONResponse:
        return _not_implemented(detail="fleet/status")

    @clanks.get("", summary="List clanks (not implemented)", description=_STAGE_NOTE)
    @clanks.get("/", include_in_schema=False)
    def list_clanks() -> JSONResponse:
        return _not_implemented(detail="clanks")

    @clanks.get("/{clank_id}", summary="Get clank (not implemented)", description=_STAGE_NOTE)
    def get_clank(clank_id: str) -> JSONResponse:
        return _not_implemented(detail=f"clanks/{clank_id}")

    @clanks.get(
        "/{clank_id}/health",
        summary="Clank health (not implemented)",
        description=_STAGE_NOTE,
    )
    def clank_health(clank_id: str) -> JSONResponse:
        return _not_implemented(detail=f"clanks/{clank_id}/health")

    @clanks.get(
        "/{clank_id}/runs",
        summary="Clank runs (not implemented)",
        description=_STAGE_NOTE,
    )
    def clank_runs(clank_id: str) -> JSONResponse:
        return _not_implemented(detail=f"clanks/{clank_id}/runs")

    @clanks.get(
        "/{clank_id}/collectors",
        summary="Clank collectors (not implemented)",
        description=_STAGE_NOTE,
    )
    def clank_collectors(clank_id: str) -> JSONResponse:
        return _not_implemented(detail=f"clanks/{clank_id}/collectors")

    @clanks.post(
        "/{clank_id}/actions",
        summary="Clank actions (not implemented)",
        description=_STAGE_NOTE,
    )
    def clank_actions(clank_id: str) -> JSONResponse:
        return _not_implemented(detail=f"clanks/{clank_id}/actions")

    for router, name in (
        (records, "records"),
        (events, "events"),
        (entities, "entities"),
        (evidence, "evidence"),
        (review, "review"),
        (backups, "backups"),
        (deployments, "deployments"),
        (ingestion, "ingestion"),
        (search, "search"),
    ):
        _add_stub_collection(router, name)

    app.include_router(system)
    app.include_router(fleet)
    app.include_router(clanks)
    app.include_router(records)
    app.include_router(events)
    app.include_router(entities)
    app.include_router(evidence)
    app.include_router(review)
    app.include_router(backups)
    app.include_router(deployments)
    app.include_router(ingestion)
    app.include_router(search)
