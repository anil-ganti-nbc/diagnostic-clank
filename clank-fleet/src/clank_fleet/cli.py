"""Fleet CLI skeleton (Stage 0.5).

Operational commands exit with code 78 and print a consistent error envelope.
No Docker, SSH, HTTP, NAS, or database calls.
"""

from __future__ import annotations

import json

import typer

from clank_fleet import API_CONTRACT_VERSION, __version__

# Documented not-implemented exit code for operational commands.
# 78 is traditionally EX_CONFIG in sysexits.h; we reuse it as STAGE0_NOT_IMPLEMENTED.
EXIT_NOT_IMPLEMENTED = 78

app = typer.Typer(
    name="clank",
    help=(
        "Clank Fleet CLI (Stage 0.5 skeleton).\n\n"
        "Operational commands are non-functional and exit with code 78.\n"
        "See OPERATIONS.md and ARCHITECTURE_PRINCIPLES.md."
    ),
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
)


def _not_implemented(command: str, *, clank_id: str | None = None) -> None:
    envelope = {
        "error_code": "STAGE0_NOT_IMPLEMENTED",
        "message": f"Command '{command}' is not implemented in Stage 0.5",
        "details": {
            "stage": "0.5",
            "command": command,
            "clank_id": clank_id,
            "api_contract_version": API_CONTRACT_VERSION,
            "hint": "See OPERATIONS.md and ARCHITECTURE_PRINCIPLES.md for planned stages.",
        },
    }
    typer.echo(json.dumps(envelope, indent=2), err=True)
    raise typer.Exit(code=EXIT_NOT_IMPLEMENTED)


@app.command("version")
def version_cmd() -> None:
    """Report CLI, package, and API contract versions."""
    typer.echo(f"clank-fleet {__version__}")
    typer.echo(f"api_contract_version {API_CONTRACT_VERSION}")
    typer.echo("Stage 0.5 skeleton — no operational control plane is active.")


@app.command()
def status(
    clank_id: str | None = typer.Argument(
        None,
        help="Optional clank id. Omitted = fleet-wide (when implemented).",
    ),
) -> None:
    """Retrieve status (not implemented)."""
    _not_implemented("status", clank_id=clank_id)


@app.command()
def doctor() -> None:
    """Run diagnostic checks (not implemented)."""
    _not_implemented("doctor")


@app.command()
def logs(
    clank_id: str = typer.Argument(..., help="Clank identifier."),
    lines: int = typer.Option(100, "--lines", "-n", help="Number of log lines (future)."),
) -> None:
    """Retrieve logs (not implemented)."""
    _ = lines  # accepted for forward-compatible CLI shape only
    _not_implemented("logs", clank_id=clank_id)


@app.command()
def deploy(
    clank_id: str = typer.Argument(..., help="Clank identifier."),
) -> None:
    """Deploy a clank (not implemented)."""
    _not_implemented("deploy", clank_id=clank_id)


@app.command()
def backup(
    clank_id: str | None = typer.Argument(
        None,
        help="Optional clank id. Omitted = fleet-wide (when implemented).",
    ),
) -> None:
    """Create a backup (not implemented)."""
    _not_implemented("backup", clank_id=clank_id)


@app.command()
def restore(
    clank_id: str | None = typer.Argument(
        None,
        help="Optional clank id. Omitted = fleet-wide (when implemented).",
    ),
) -> None:
    """Restore from backup (not implemented)."""
    _not_implemented("restore", clank_id=clank_id)


@app.command()
def health(
    clank_id: str | None = typer.Argument(
        None,
        help="Optional clank id. Omitted = fleet-wide (when implemented).",
    ),
) -> None:
    """Report health (not implemented)."""
    _not_implemented("health", clank_id=clank_id)


@app.command()
def run(
    clank_id: str = typer.Argument(..., help="Clank identifier."),
) -> None:
    """Trigger a run-now (not implemented)."""
    _not_implemented("run", clank_id=clank_id)


@app.command()
def pause(
    clank_id: str = typer.Argument(..., help="Clank identifier."),
) -> None:
    """Pause a clank (not implemented)."""
    _not_implemented("pause", clank_id=clank_id)


@app.command()
def resume(
    clank_id: str = typer.Argument(..., help="Clank identifier."),
) -> None:
    """Resume a clank (not implemented)."""
    _not_implemented("resume", clank_id=clank_id)


@app.command()
def restart(
    clank_id: str = typer.Argument(..., help="Clank identifier."),
) -> None:
    """Restart a clank (not implemented)."""
    _not_implemented("restart", clank_id=clank_id)


@app.command()
def rollback(
    clank_id: str = typer.Argument(..., help="Clank identifier."),
) -> None:
    """Rollback a clank deployment (not implemented)."""
    _not_implemented("rollback", clank_id=clank_id)


if __name__ == "__main__":
    app()


# --- Stage 1A read-only fleet commands ---------------------------------------

fleet_app = typer.Typer(name="fleet", help="Stage 1A read-only Fleet inspection.")
app.add_typer(fleet_app, name="fleet")


def _registry_from_env():
    from clank_fleet.adapters.factory import build_default_registry

    return build_default_registry()


@fleet_app.command("list")
def fleet_list(
    json_out: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """List registered Clanks and operational state."""
    registry = _registry_from_env()
    rows = registry.fleet_summary()
    if json_out:
        typer.echo(json.dumps({"clanks": rows}, indent=2, default=str))
        return
    if not rows:
        typer.echo("No Clanks registered.")
        return
    typer.echo("CLANK FLEET")
    typer.echo("")
    for row in rows:
        stale = " (STALE)" if row.get("is_stale") else ""
        typer.echo(f"{row['clank_id']}")
        typer.echo(f"  state: {row['operational_state']}{stale}")
        typer.echo(f"  delivery visibility: {row['delivery_visibility']}")
        if row.get("message"):
            typer.echo(f"  note: {row['message']}")
        typer.echo("")


@fleet_app.command("status")
def fleet_status(
    clank_id: str = typer.Argument(..., help="Clank id"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Show status for one Clank."""
    registry = _registry_from_env()
    try:
        registry.get(clank_id)
    except KeyError:
        typer.echo(json.dumps({"error": "unknown_clank", "clank_id": clank_id}), err=True)
        raise typer.Exit(code=2)
    status_row = registry.safe_status(clank_id)
    data = status_row.model_dump(mode="json")
    if json_out:
        typer.echo(json.dumps(data, indent=2, default=str))
    else:
        typer.echo(json.dumps(data, indent=2, default=str))


@fleet_app.command("health")
def fleet_health(
    clank_id: str = typer.Argument(...),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Show health envelope for one Clank."""
    registry = _registry_from_env()
    if clank_id not in registry.list_ids():
        typer.echo(json.dumps({"error": "unknown_clank", "clank_id": clank_id}), err=True)
        raise typer.Exit(code=2)
    health = registry.safe_health(clank_id)
    typer.echo(json.dumps(health.model_dump(mode="json"), indent=2, default=str))


@fleet_app.command("telemetry")
def fleet_telemetry(
    clank_id: str = typer.Argument(...),
    limit: int = typer.Option(10, "--limit", "-n"),
) -> None:
    """Show recent telemetry for one Clank."""
    registry = _registry_from_env()
    if clank_id not in registry.list_ids():
        typer.echo(json.dumps({"error": "unknown_clank", "clank_id": clank_id}), err=True)
        raise typer.Exit(code=2)
    rows = registry.safe_telemetry(clank_id, limit=limit)
    typer.echo(
        json.dumps(
            {"clank_id": clank_id, "telemetry": [r.model_dump(mode="json") for r in rows]},
            indent=2,
            default=str,
        )
    )
