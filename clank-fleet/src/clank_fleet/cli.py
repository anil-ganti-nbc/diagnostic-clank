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
