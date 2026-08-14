"""Route registration for Fleet API (Stage 1A).

Read-only clank inspection routes are live. Mutation and domain routes
remain 501 until later stages.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.responses import JSONResponse

from clank_fleet.fleet_api.models import NotImplementedResponse, PingResponse

_STAGE_NOTE = "Stage 1A — mutation/domain routes remain 501."


def _not_implemented(*, detail: str | None = None) -> JSONResponse:
    body = NotImplementedResponse(
        details={"hint": detail} if detail else {},
    )
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content=body.model_dump(),
    )


def _add_stub_collection(router: APIRouter, resource_name: str) -> None:
    @router.get("", summary=f"List {resource_name} (not implemented)", description=_STAGE_NOTE)
    @router.get("/", include_in_schema=False)
    def collection_root() -> JSONResponse:
        return _not_implemented(detail=f"{resource_name} collection")

    @router.get("/{item_id}", summary=f"Get {resource_name} item (not implemented)", description=_STAGE_NOTE)
    def collection_item(item_id: str) -> JSONResponse:
        return _not_implemented(detail=f"{resource_name}/{item_id}")


def _get_registry(request: Request):
    registry = getattr(request.app.state, "fleet_registry", None)
    if registry is None:
        from clank_fleet.adapters.factory import build_default_registry

        registry = build_default_registry()
        request.app.state.fleet_registry = registry
    return registry


def register_routes(app: FastAPI) -> None:
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

    @system.get("/ping", summary="Process-level shell check")
    def ping() -> PingResponse:
        return PingResponse(
            status="ok",
            message="Stage 1A Fleet API shell — read-only clank routes enabled",
        )

    @fleet.get("/summary", summary="Fleet aggregate summary")
    def fleet_summary(request: Request) -> dict[str, Any]:
        registry = _get_registry(request)
        return {"clanks": registry.fleet_summary()}

    @clanks.get("", summary="List registered clanks")
    @clanks.get("/", include_in_schema=False)
    def list_clanks(request: Request) -> dict[str, Any]:
        registry = _get_registry(request)
        items = []
        for clank_id in registry.list_ids():
            reg = registry.get(clank_id)
            identity = reg.adapter.identity()
            status_row = registry.safe_status(clank_id)
            items.append(
                {
                    "clank_id": clank_id,
                    "display_name": identity.display_name,
                    "clank_version": identity.clank_version,
                    "release_channel": identity.release_channel.value,
                    "operational_state": status_row.operational_state.value,
                    "is_stale": status_row.is_stale,
                    "capabilities": identity.capabilities.model_dump(),
                }
            )
        return {"clanks": items}

    @clanks.get("/{clank_id}", summary="Clank detail", response_model=None)
    def get_clank(clank_id: str, request: Request):
        registry = _get_registry(request)
        try:
            reg = registry.get(clank_id)
        except KeyError:
            return JSONResponse(status_code=404, content={"error": "unknown_clank", "clank_id": clank_id})
        identity = reg.adapter.identity()
        status_row = registry.safe_status(clank_id)
        return {
            "identity": identity.model_dump(mode="json"),
            "status": status_row.model_dump(mode="json"),
            "last_run": reg.adapter.last_run(),
        }

    @clanks.get("/{clank_id}/health", summary="Clank health envelope", response_model=None)
    def clank_health(clank_id: str, request: Request):
        registry = _get_registry(request)
        if clank_id not in registry.list_ids():
            return JSONResponse(status_code=404, content={"error": "unknown_clank", "clank_id": clank_id})
        health = registry.safe_health(clank_id)
        return health.model_dump(mode="json")

    @clanks.get("/{clank_id}/telemetry", summary="Recent telemetry envelopes", response_model=None)
    def clank_telemetry(clank_id: str, request: Request):
        registry = _get_registry(request)
        if clank_id not in registry.list_ids():
            return JSONResponse(status_code=404, content={"error": "unknown_clank", "clank_id": clank_id})
        rows = registry.safe_telemetry(clank_id)
        return {"clank_id": clank_id, "telemetry": [r.model_dump(mode="json") for r in rows]}

    @clanks.get("/{clank_id}/sources", summary="Source summary", response_model=None)
    def clank_sources(clank_id: str, request: Request):
        registry = _get_registry(request)
        if clank_id not in registry.list_ids():
            return JSONResponse(status_code=404, content={"error": "unknown_clank", "clank_id": clank_id})
        return {"clank_id": clank_id, "sources": registry.safe_sources(clank_id)}

    # Still not implemented for Stage 1A
    @clanks.get("/{clank_id}/runs", summary="Clank runs (not fully implemented)")
    def clank_runs(clank_id: str) -> JSONResponse:
        return _not_implemented(detail=f"clanks/{clank_id}/runs")

    @clanks.get("/{clank_id}/collectors", summary="Collectors (not implemented)")
    def clank_collectors(clank_id: str) -> JSONResponse:
        return _not_implemented(detail=f"clanks/{clank_id}/collectors")

    @clanks.post("/{clank_id}/actions", summary="Clank actions (not implemented)")
    def clank_actions(clank_id: str) -> JSONResponse:
        return _not_implemented(detail=f"clanks/{clank_id}/actions")

    @fleet.get("", summary="Fleet root (not implemented)")
    @fleet.get("/", include_in_schema=False)
    def fleet_root() -> JSONResponse:
        return _not_implemented(detail="fleet")

    @fleet.get("/status", summary="Fleet status (use /summary)")
    def fleet_status() -> JSONResponse:
        return _not_implemented(detail="fleet/status — use /api/v1/fleet/summary")

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
